"use client";

import { useMemo, useState } from "react";

export interface InterviewState {
  currentIndex: number;
  isComplete: boolean;
}

export function useInterview(totalQuestions: number): {
  state: InterviewState;
  goToNextQuestion: () => void;
  resetInterview: () => void;
} {
  const [currentIndex, setCurrentIndex] = useState<number>(0);

  const state = useMemo<InterviewState>(
    () => ({
      currentIndex,
      isComplete: totalQuestions > 0 && currentIndex >= totalQuestions,
    }),
    [currentIndex, totalQuestions],
  );

  function goToNextQuestion(): void {
    setCurrentIndex((previousIndex) => previousIndex + 1);
  }

  function resetInterview(): void {
    setCurrentIndex(0);
  }

  return { state, goToNextQuestion, resetInterview };
}
