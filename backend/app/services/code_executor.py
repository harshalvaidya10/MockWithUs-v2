from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, TypedDict


EXECUTION_ROOT = Path("/tmp/mockwithus_exec")
DEFAULT_TIMEOUT_SECONDS = 10

STATUS_ACCEPTED = "accepted"
STATUS_WRONG_ANSWER = "wrong_answer"
STATUS_RUNTIME_ERROR = "runtime_error"
STATUS_TIME_LIMIT = "time_limit"
STATUS_COMPILATION_ERROR = "compilation_error"

SUPPORTED_LANGUAGES = {"python", "javascript", "java", "cpp"}


class RawExecutionResult(TypedDict):
    actual_output: str | None
    runtime_ms: int | None
    error_output: str | None
    status: str


class TestExecutionResult(TypedDict):
    test_case_id: Any
    passed: bool
    actual_output: str | None
    expected_output: str | None
    runtime_ms: int | None
    error_output: str | None
    status: str


def _ensure_execution_root() -> None:
    EXECUTION_ROOT.mkdir(parents=True, exist_ok=True)


def _runtime_command(language: str) -> str | None:
    if language == "python":
        return "python3"
    if language == "javascript":
        return "node"
    if language == "java":
        return "java"
    if language == "cpp":
        return "g++"
    return None


def is_language_available(language: str) -> bool:
    command = _runtime_command(language)
    if command is None:
        return False

    if language == "java":
        return shutil.which("javac") is not None and shutil.which("java") is not None
    return shutil.which(command) is not None


def _as_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _normalize_output(value: str | None) -> str:
    if value is None:
        return ""
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"))


def _build_python_script(*, source_code: str, function_name: str) -> str:
    return f"""import json
import sys

{source_code}


def __is_argument_mismatch(error: TypeError) -> bool:
    message = str(error)
    mismatch_markers = (
        "positional argument",
        "required positional",
        "unexpected keyword",
        "keyword argument",
        "takes ",
        "were given",
    )
    return any(marker in message for marker in mismatch_markers)


def __invoke(function_name: str, payload):
    function = globals().get(function_name)
    if not callable(function):
        raise NameError(f"Function '{{function_name}}' was not found in submitted code.")
    if isinstance(payload, list):
        try:
            return function(*payload)
        except TypeError as error:
            if __is_argument_mismatch(error):
                return function(payload)
            raise
    if isinstance(payload, dict):
        try:
            return function(**payload)
        except TypeError as error:
            if __is_argument_mismatch(error):
                return function(payload)
            raise
    return function(payload)


if __name__ == "__main__":
    raw_input = sys.stdin.read()
    payload = json.loads(raw_input) if raw_input.strip() else None
    result = __invoke("{function_name}", payload)
    print(json.dumps(result))
"""


def _build_javascript_script(*, source_code: str, function_name: str) -> str:
    return f"""const fs = require("fs");

{source_code}

function invoke(functionName, payload) {{
  let fn = globalThis[functionName];
  if (typeof fn !== "function" && typeof module !== "undefined" && module.exports) {{
    fn = module.exports[functionName];
  }}
  if (typeof fn !== "function") {{
    try {{
      fn = eval(functionName);
    }} catch (_error) {{
      fn = undefined;
    }}
  }}
  if (typeof fn !== "function") {{
    throw new Error(`Function ${{functionName}} was not found in submitted code.`);
  }}
  if (Array.isArray(payload)) {{
    return fn(...payload);
  }}
  if (payload !== null && typeof payload === "object") {{
    return fn(payload);
  }}
  return fn(payload);
}}

(async () => {{
  const rawInput = fs.readFileSync(0, "utf8");
  const payload = rawInput.trim().length ? JSON.parse(rawInput) : null;
  const result = await invoke("{function_name}", payload);
  process.stdout.write(JSON.stringify(result));
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
}});
"""


def _split_parameter_chunks(parameter_text: str) -> list[str]:
    if not parameter_text.strip():
        return []

    chunks: list[str] = []
    current: list[str] = []
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0

    for char in parameter_text:
        if char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)

        if char == "," and angle_depth == 0 and paren_depth == 0 and bracket_depth == 0:
            piece = "".join(current).strip()
            if piece:
                chunks.append(piece)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        chunks.append(tail)
    return chunks


def _extract_parameter_types(parameter_text: str) -> list[str]:
    types: list[str] = []
    for chunk in _split_parameter_chunks(parameter_text):
        piece = chunk.strip()
        if not piece:
            continue
        tokens = piece.split()
        if len(tokens) <= 1:
            types.append(piece)
            continue
        candidate = " ".join(tokens[:-1]).strip()
        types.append(candidate or piece)
    return types


def _contains_java_main_method(source_code: str) -> bool:
    return re.search(r"\bpublic\s+static\s+void\s+main\s*\(", source_code) is not None


def _contains_cpp_main_method(source_code: str) -> bool:
    return re.search(r"\bint\s+main\s*\(", source_code) is not None


def _detect_java_class_name(source_code: str) -> str:
    public_match = re.search(r"\bpublic\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", source_code)
    if public_match:
        return public_match.group(1)
    class_match = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", source_code)
    if class_match:
        return class_match.group(1)
    return "Main"


def _java_inferred_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "String"
    if isinstance(value, list):
        if not value:
            return "int[]"
        nested_types = [_java_inferred_type(item) for item in value]
        first = nested_types[0]
        if all(item_type == first for item_type in nested_types):
            return f"{first}[]"
        return "Object[]"
    return "Object"


def _java_literal(value: Any, declared_type: str) -> str:
    normalized_type = declared_type.replace("final ", "").replace("...", "[]").strip()

    if value is None:
        return "null"

    if normalized_type.endswith("[]"):
        if not isinstance(value, list):
            return "null"
        inner_type = normalized_type[:-2].strip() or "Object"
        items = ", ".join(_java_literal(item, inner_type) for item in value)
        return f"new {normalized_type}{{{items}}}"

    lowered = normalized_type.lower()
    if lowered in {"int", "integer", "short", "byte"}:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"
    if lowered in {"long"}:
        try:
            return f"{int(value)}L"
        except (TypeError, ValueError):
            return "0L"
    if lowered in {"double", "float"}:
        try:
            rendered = repr(float(value))
        except (TypeError, ValueError):
            rendered = "0.0"
        return rendered
    if lowered in {"boolean", "bool"}:
        return "true" if bool(value) else "false"
    if "string" in lowered or lowered == "charsequence":
        return json.dumps(str(value))
    if lowered == "char":
        as_text = str(value)
        if not as_text:
            return "'\\0'"
        escaped = as_text[0].replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if lowered == "object":
        inferred = _java_inferred_type(value)
        return _java_literal(value, inferred)

    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return _java_literal(value, "Object[]")
    return "null"


def _build_java_runner_source(
    *,
    class_name: str,
    function_name: str,
    input_data: Any,
    params_signature: str,
) -> str:
    args = input_data if isinstance(input_data, list) else [input_data]
    param_types = _extract_parameter_types(params_signature)
    if len(param_types) != len(args):
        param_types = [_java_inferred_type(value) for value in args]
    else:
        param_types = [param_type.replace("...", "[]").strip() or "Object" for param_type in param_types]

    declarations: list[str] = []
    arg_names: list[str] = []
    for index, (arg_value, declared_type) in enumerate(zip(args, param_types)):
        arg_name = f"arg{index}"
        arg_names.append(arg_name)
        declarations.append(f"        {declared_type} {arg_name} = {_java_literal(arg_value, declared_type)};")

    invocation_args = ", ".join(arg_names)

    return f"""import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;

public class Runner {{
    private static String escapeJson(String value) {{
        StringBuilder escaped = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {{
            char ch = value.charAt(i);
            switch (ch) {{
                case '\\\\' -> escaped.append("\\\\\\\\");
                case '\"' -> escaped.append("\\\\\\"");
                case '\\n' -> escaped.append("\\\\n");
                case '\\r' -> escaped.append("\\\\r");
                case '\\t' -> escaped.append("\\\\t");
                default -> escaped.append(ch);
            }}
        }}
        return escaped.toString();
    }}

    private static String toJson(Object value) {{
        if (value == null) {{
            return "null";
        }}
        if (value instanceof String || value instanceof Character) {{
            return "\\"\" + escapeJson(String.valueOf(value)) + "\\"";
        }}
        if (value instanceof Number || value instanceof Boolean) {{
            return String.valueOf(value);
        }}
        Class<?> clazz = value.getClass();
        if (clazz.isArray()) {{
            int length = Array.getLength(value);
            StringBuilder builder = new StringBuilder("[");
            for (int i = 0; i < length; i++) {{
                if (i > 0) {{
                    builder.append(",");
                }}
                builder.append(toJson(Array.get(value, i)));
            }}
            builder.append("]");
            return builder.toString();
        }}
        if (value instanceof Iterable<?> iterable) {{
            StringBuilder builder = new StringBuilder("[");
            boolean first = true;
            for (Object item : iterable) {{
                if (!first) {{
                    builder.append(",");
                }}
                first = false;
                builder.append(toJson(item));
            }}
            builder.append("]");
            return builder.toString();
        }}
        return "\\"\" + escapeJson(String.valueOf(value)) + "\\"";
    }}

    public static void main(String[] args) throws Exception {{
        Class<?> targetClass = Class.forName("{class_name}");
        Method targetMethod = null;
        for (Method method : targetClass.getDeclaredMethods()) {{
            if (method.getName().equals("{function_name}") && method.getParameterCount() == {len(args)}) {{
                targetMethod = method;
                break;
            }}
        }}
        if (targetMethod == null) {{
            throw new RuntimeException("Function '{function_name}' was not found.");
        }}
        targetMethod.setAccessible(true);
{chr(10).join(declarations) if declarations else "        // No arguments"}
        Object receiver = Modifier.isStatic(targetMethod.getModifiers())
            ? null
            : targetClass.getDeclaredConstructor().newInstance();
        Object result = targetMethod.invoke(receiver, new Object[]{{{invocation_args}}});
        System.out.print(toJson(result));
    }}
}}
"""


def _strip_cpp_modifiers(type_name: str) -> str:
    normalized = type_name.strip()
    normalized = re.sub(r"\bconst\b", "", normalized)
    normalized = normalized.replace("&", "").replace("*", "").strip()
    return re.sub(r"\s+", " ", normalized)


def _extract_cpp_vector_inner_type(type_name: str) -> str | None:
    cleaned = type_name.strip()
    if not cleaned.startswith("vector<") or not cleaned.endswith(">"):
        return None
    depth = 0
    content: list[str] = []
    for char in cleaned[len("vector<") : -1]:
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        content.append(char)
    return "".join(content).strip() if content else None


def _cpp_inferred_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if not value:
            return "vector<int>"
        nested_types = [_cpp_inferred_type(item) for item in value]
        first = nested_types[0]
        if all(item_type == first for item_type in nested_types):
            return f"vector<{first}>"
        return "vector<int>"
    return "int"


def _cpp_literal(value: Any, declared_type: str) -> str:
    normalized_type = _strip_cpp_modifiers(declared_type)
    if value is None:
        return "{}"

    vector_inner = _extract_cpp_vector_inner_type(normalized_type)
    if vector_inner is not None:
        if not isinstance(value, list):
            return "{}"
        items = ", ".join(_cpp_literal(item, vector_inner) for item in value)
        return f"{{{items}}}"

    lowered = normalized_type.lower()
    if lowered in {"int", "short", "long", "long long", "size_t"}:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"
    if lowered in {"double", "float"}:
        try:
            return repr(float(value))
        except (TypeError, ValueError):
            return "0.0"
    if lowered in {"bool"}:
        return "true" if bool(value) else "false"
    if lowered in {"string", "std::string"}:
        return json.dumps(str(value))
    if lowered in {"char"}:
        as_text = str(value)
        if not as_text:
            return "'\\0'"
        escaped = as_text[0].replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        inferred = _cpp_inferred_type(value)
        return _cpp_literal(value, inferred)
    return "{}"


def _build_cpp_runner_source(
    *,
    source_code: str,
    function_name: str,
    input_data: Any,
    params_signature: str,
) -> str:
    args = input_data if isinstance(input_data, list) else [input_data]
    param_types = _extract_parameter_types(params_signature)
    if len(param_types) != len(args):
        param_types = [_cpp_inferred_type(value) for value in args]
    else:
        param_types = [param_type.strip() or "int" for param_type in param_types]

    declarations: list[str] = []
    arg_names: list[str] = []
    for index, (arg_value, declared_type) in enumerate(zip(args, param_types)):
        arg_name = f"arg{index}"
        arg_names.append(arg_name)
        cleaned_type = _strip_cpp_modifiers(declared_type) or "int"
        declarations.append(f"    {cleaned_type} {arg_name} = {_cpp_literal(arg_value, cleaned_type)};")

    invocation_args = ", ".join(arg_names)
    invoke_line = f"    auto result = {function_name}({invocation_args});"

    return f"""#include <bits/stdc++.h>
using namespace std;

{source_code}

template <typename T>
struct is_vector : false_type {{}};

template <typename T, typename Allocator>
struct is_vector<vector<T, Allocator>> : true_type {{}};

string escape_json(const string& value) {{
    string out;
    out.reserve(value.size());
    for (char ch : value) {{
        switch (ch) {{
            case '\\\\': out += "\\\\\\\\"; break;
            case '\"': out += "\\\\\\""; break;
            case '\\n': out += "\\\\n"; break;
            case '\\r': out += "\\\\r"; break;
            case '\\t': out += "\\\\t"; break;
            default: out += ch; break;
        }}
    }}
    return out;
}}

template <typename T>
string to_json(const T& value) {{
    if constexpr (is_same_v<T, string>) {{
        return "\\"\" + escape_json(value) + "\\"";
    }} else if constexpr (is_same_v<T, const char*>) {{
        return "\\"\" + escape_json(string(value)) + "\\"";
    }} else if constexpr (is_same_v<T, char>) {{
        return "\\"\" + escape_json(string(1, value)) + "\\"";
    }} else if constexpr (is_same_v<T, bool>) {{
        return value ? "true" : "false";
    }} else if constexpr (is_arithmetic_v<T>) {{
        ostringstream out;
        out << value;
        return out.str();
    }} else if constexpr (is_vector<T>::value) {{
        string out = "[";
        for (size_t i = 0; i < value.size(); ++i) {{
            if (i > 0) {{
                out += ",";
            }}
            out += to_json(value[i]);
        }}
        out += "]";
        return out;
    }} else {{
        return "\\"unsupported\\"";
    }}
}}

int main() {{
{chr(10).join(declarations) if declarations else "    // No arguments"}
{invoke_line}
    cout << to_json(result);
    return 0;
}}
"""


def _run_process(
    *,
    command: list[str],
    stdin_payload: str,
    timeout_seconds: int,
    cwd: Path | None = None,
) -> RawExecutionResult:
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=stdin_payload,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=str(cwd) if cwd is not None else None,
            check=False,
        )
    except FileNotFoundError as exc:
        runtime_name = command[0]
        return RawExecutionResult(
            actual_output=None,
            runtime_ms=None,
            error_output=f"{runtime_name} runtime is not installed.",
            status=STATUS_RUNTIME_ERROR,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return RawExecutionResult(
            actual_output=(exc.stdout or None),
            runtime_ms=elapsed_ms,
            error_output=(exc.stderr or f"Execution exceeded {timeout_seconds} seconds."),
            status=STATUS_TIME_LIMIT,
        )

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    if completed.returncode != 0:
        return RawExecutionResult(
            actual_output=completed.stdout or None,
            runtime_ms=elapsed_ms,
            error_output=completed.stderr or "Execution failed.",
            status=STATUS_RUNTIME_ERROR,
        )
    return RawExecutionResult(
        actual_output=completed.stdout,
        runtime_ms=elapsed_ms,
        error_output=completed.stderr or None,
        status=STATUS_ACCEPTED,
    )


def _execute_python_or_javascript(
    *,
    language: str,
    source_code: str,
    function_name: str,
    input_data: Any,
    timeout_seconds: int,
) -> RawExecutionResult:
    _ensure_execution_root()
    execution_id = uuid.uuid4().hex
    extension = "py" if language == "python" else "js"
    script_path = EXECUTION_ROOT / f"{execution_id}.{extension}"
    script_content = (
        _build_python_script(source_code=source_code, function_name=function_name)
        if language == "python"
        else _build_javascript_script(source_code=source_code, function_name=function_name)
    )

    runtime_command = "python3" if language == "python" else "node"
    if shutil.which(runtime_command) is None:
        return RawExecutionResult(
            actual_output=None,
            runtime_ms=None,
            error_output=f"{runtime_command} runtime is not installed.",
            status=STATUS_RUNTIME_ERROR,
        )

    try:
        script_path.write_text(script_content, encoding="utf-8")
        return _run_process(
            command=[runtime_command, str(script_path)],
            stdin_payload=_as_json_text(input_data),
            timeout_seconds=timeout_seconds,
        )
    finally:
        script_path.unlink(missing_ok=True)


def _execute_java(
    *,
    source_code: str,
    input_data: Any,
    function_name: str,
    params_signature: str,
    timeout_seconds: int,
) -> RawExecutionResult:
    if shutil.which("javac") is None or shutil.which("java") is None:
        return RawExecutionResult(
            actual_output=None,
            runtime_ms=None,
            error_output="Java runtime is not installed (javac/java required).",
            status=STATUS_COMPILATION_ERROR,
        )

    _ensure_execution_root()
    execution_dir = EXECUTION_ROOT / uuid.uuid4().hex
    execution_dir.mkdir(parents=True, exist_ok=True)
    class_name = _detect_java_class_name(source_code)
    source_path = execution_dir / f"{class_name}.java"
    has_main = _contains_java_main_method(source_code)
    try:
        source_path.write_text(source_code, encoding="utf-8")
        compile_command = ["javac", str(source_path)]
        run_command = ["java", "-cp", str(execution_dir), class_name]
        stdin_payload = _as_json_text(input_data)

        if not has_main:
            runner_path = execution_dir / "Runner.java"
            runner_source = _build_java_runner_source(
                class_name=class_name,
                function_name=function_name,
                input_data=input_data,
                params_signature=params_signature,
            )
            runner_path.write_text(runner_source, encoding="utf-8")
            compile_command = ["javac", str(source_path), str(runner_path)]
            run_command = ["java", "-cp", str(execution_dir), "Runner"]
            stdin_payload = ""

        compile_result = _run_process(
            command=compile_command,
            stdin_payload="",
            timeout_seconds=timeout_seconds,
            cwd=execution_dir,
        )
        if compile_result["status"] != STATUS_ACCEPTED:
            return RawExecutionResult(
                actual_output=compile_result["actual_output"],
                runtime_ms=compile_result["runtime_ms"],
                error_output=compile_result["error_output"],
                status=STATUS_COMPILATION_ERROR,
            )
        return _run_process(
            command=run_command,
            stdin_payload=stdin_payload,
            timeout_seconds=timeout_seconds,
            cwd=execution_dir,
        )
    finally:
        shutil.rmtree(execution_dir, ignore_errors=True)


def _execute_cpp(
    *,
    source_code: str,
    input_data: Any,
    function_name: str,
    params_signature: str,
    timeout_seconds: int,
) -> RawExecutionResult:
    if shutil.which("g++") is None:
        return RawExecutionResult(
            actual_output=None,
            runtime_ms=None,
            error_output="C++ compiler is not installed (g++ required).",
            status=STATUS_COMPILATION_ERROR,
        )

    _ensure_execution_root()
    execution_dir = EXECUTION_ROOT / uuid.uuid4().hex
    execution_dir.mkdir(parents=True, exist_ok=True)
    source_path = execution_dir / "main.cpp"
    binary_path = execution_dir / "main.out"
    try:
        has_main = _contains_cpp_main_method(source_code)
        source_to_compile = source_code
        stdin_payload = _as_json_text(input_data)
        if not has_main:
            source_to_compile = _build_cpp_runner_source(
                source_code=source_code,
                function_name=function_name,
                input_data=input_data,
                params_signature=params_signature,
            )
            stdin_payload = ""

        source_path.write_text(source_to_compile, encoding="utf-8")
        compile_result = _run_process(
            command=["g++", str(source_path), "-std=c++17", "-O2", "-o", str(binary_path)],
            stdin_payload="",
            timeout_seconds=timeout_seconds,
            cwd=execution_dir,
        )
        if compile_result["status"] != STATUS_ACCEPTED:
            return RawExecutionResult(
                actual_output=compile_result["actual_output"],
                runtime_ms=compile_result["runtime_ms"],
                error_output=compile_result["error_output"],
                status=STATUS_COMPILATION_ERROR,
            )
        return _run_process(
            command=[str(binary_path)],
            stdin_payload=stdin_payload,
            timeout_seconds=timeout_seconds,
            cwd=execution_dir,
        )
    finally:
        shutil.rmtree(execution_dir, ignore_errors=True)


def execute_code_once(
    *,
    language: str,
    source_code: str,
    function_name: str,
    input_data: Any,
    language_signature: dict[str, Any] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> RawExecutionResult:
    """Execute source code once for a single input payload."""
    normalized_language = (language or "").strip().lower()
    if normalized_language not in SUPPORTED_LANGUAGES:
        return RawExecutionResult(
            actual_output=None,
            runtime_ms=None,
            error_output=f"Unsupported language '{language}'.",
            status=STATUS_RUNTIME_ERROR,
        )

    if normalized_language in {"python", "javascript"}:
        return _execute_python_or_javascript(
            language=normalized_language,
            source_code=source_code,
            function_name=function_name,
            input_data=input_data,
            timeout_seconds=timeout_seconds,
        )
    if normalized_language == "java":
        params_signature = ""
        if isinstance(language_signature, dict):
            params_signature = str(language_signature.get("params", "")).strip()
        return _execute_java(
            source_code=source_code,
            input_data=input_data,
            function_name=function_name,
            params_signature=params_signature,
            timeout_seconds=timeout_seconds,
        )
    params_signature = ""
    if isinstance(language_signature, dict):
        params_signature = str(language_signature.get("params", "")).strip()
    return _execute_cpp(
        source_code=source_code,
        input_data=input_data,
        function_name=function_name,
        params_signature=params_signature,
        timeout_seconds=timeout_seconds,
    )


def execute_test_case(
    *,
    language: str,
    source_code: str,
    function_name: str,
    input_data: Any,
    expected_output: Any,
    language_signature: dict[str, Any] | None = None,
    test_case_id: Any = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> TestExecutionResult:
    """Execute one test case and compare output against expected result."""
    execution = execute_code_once(
        language=language,
        source_code=source_code,
        function_name=function_name,
        input_data=input_data,
        language_signature=language_signature,
        timeout_seconds=timeout_seconds,
    )
    expected_text = _as_json_text(expected_output)
    if execution["status"] != STATUS_ACCEPTED:
        return TestExecutionResult(
            test_case_id=test_case_id,
            passed=False,
            actual_output=execution["actual_output"],
            expected_output=expected_text,
            runtime_ms=execution["runtime_ms"],
            error_output=execution["error_output"],
            status=execution["status"],
        )

    passed = _normalize_output(execution["actual_output"]) == _normalize_output(expected_text)
    status = STATUS_ACCEPTED if passed else STATUS_WRONG_ANSWER
    return TestExecutionResult(
        test_case_id=test_case_id,
        passed=passed,
        actual_output=execution["actual_output"],
        expected_output=expected_text,
        runtime_ms=execution["runtime_ms"],
        error_output=execution["error_output"],
        status=status,
    )


def execute_code_submission(
    *,
    language: str,
    source_code: str,
    function_name: str,
    test_cases: list[dict[str, Any]],
    language_signature: dict[str, Any] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[TestExecutionResult]:
    """Execute submitted code against a list of test cases."""
    results: list[TestExecutionResult] = []
    for test_case in test_cases:
        result = execute_test_case(
            language=language,
            source_code=source_code,
            function_name=function_name,
            input_data=test_case.get("input_data"),
            expected_output=test_case.get("expected_output"),
            language_signature=language_signature,
            test_case_id=test_case.get("id"),
            timeout_seconds=timeout_seconds,
        )
        results.append(result)
    return results
