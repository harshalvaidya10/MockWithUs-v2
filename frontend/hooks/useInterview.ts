"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

export interface InterviewState {
  currentIndex: number;
  isComplete: boolean;
}

export function useInterview(totalQuestions: number): {
  state: InterviewState;
  goToNextQuestion: () => void;
  setCurrentIndex: (index: number) => void;
  resetInterview: () => void;
} {
  const [currentIndex, setCurrentIndex] = useState<number>(0);

  useEffect(() => {
    setCurrentIndex((previousIndex) => {
      if (totalQuestions < 0) {
        return 0;
      }
      return Math.min(Math.max(previousIndex, 0), totalQuestions);
    });
  }, [totalQuestions]);

  const state = useMemo<InterviewState>(
    () => ({
      currentIndex,
      isComplete: totalQuestions > 0 && currentIndex >= totalQuestions,
    }),
    [currentIndex, totalQuestions],
  );

  const goToNextQuestion = useCallback((): void => {
    setCurrentIndex((previousIndex) => Math.min(previousIndex + 1, totalQuestions));
  }, [totalQuestions]);

  const setCurrentQuestionIndex = useCallback(
    (index: number): void => {
      setCurrentIndex(Math.min(Math.max(index, 0), totalQuestions));
    },
    [totalQuestions],
  );

  const resetInterview = useCallback((): void => {
    setCurrentIndex(0);
  }, []);

  return { state, goToNextQuestion, setCurrentIndex: setCurrentQuestionIndex, resetInterview };
}
