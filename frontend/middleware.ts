import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE_NAME = "mockwithus_access_token";

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  const isProtectedPath =
    pathname.startsWith("/home") ||
    pathname.startsWith("/practice") ||
    pathname.startsWith("/library") ||
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/interview") ||
    pathname.startsWith("/coding") ||
    pathname.startsWith("/jobs") ||
    pathname.startsWith("/resumes");

  if (isProtectedPath) {
    const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

    if (!token) {
      const loginUrl = request.nextUrl.clone();
      loginUrl.pathname = "/login";
      loginUrl.search = "";
      const target = `${request.nextUrl.pathname}${request.nextUrl.search}`;
      loginUrl.searchParams.set("next", target);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/home/:path*",
    "/practice/:path*",
    "/library/:path*",
    "/dashboard/:path*",
    "/interview/:path*",
    "/coding/:path*",
    "/jobs/:path*",
    "/resumes/:path*",
  ],
};
