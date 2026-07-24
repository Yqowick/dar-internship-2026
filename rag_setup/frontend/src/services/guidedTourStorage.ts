const GUIDED_TOUR_STORAGE_KEY =
  "cis-controls-guided-tour-completed-v1"

export function hasCompletedGuidedTour():
  boolean {
  try {
    return (
      window.localStorage.getItem(
        GUIDED_TOUR_STORAGE_KEY,
      ) === "true"
    )
  } catch {
    return false
  }
}

export function markGuidedTourCompleted():
  void {
  try {
    window.localStorage.setItem(
      GUIDED_TOUR_STORAGE_KEY,
      "true",
    )
  } catch {
    // The tour still works when
    // browser storage is unavailable.
  }
}
