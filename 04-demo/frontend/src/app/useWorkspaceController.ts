import { useEffect, useRef, useState } from "react";

import type { BusyState } from "../contracts";

type WorkspaceControllerOptions = {
  scenarioFingerprint: string | null;
  onScenarioInvalidated: () => void;
};

export function useWorkspaceController({ scenarioFingerprint, onScenarioInvalidated }: WorkspaceControllerOptions) {
  const [busy, setBusy] = useState<BusyState>(null);
  const [error, setError] = useState<string | null>(null);
  const previousScenarioFingerprintRef = useRef<string | null>(null);
  const autoTaskViewFingerprintRef = useRef<string | null>(null);
  const invalidationHandlerRef = useRef(onScenarioInvalidated);
  invalidationHandlerRef.current = onScenarioInvalidated;

  useEffect(() => {
    if (previousScenarioFingerprintRef.current === null) {
      previousScenarioFingerprintRef.current = scenarioFingerprint;
      return;
    }
    if (previousScenarioFingerprintRef.current === scenarioFingerprint) return;
    previousScenarioFingerprintRef.current = scenarioFingerprint;
    invalidationHandlerRef.current();
  }, [scenarioFingerprint]);

  function rememberScenarioFingerprint(fingerprint: string | null) {
    previousScenarioFingerprintRef.current = fingerprint;
  }

  return {
    autoTaskViewFingerprintRef,
    busy,
    error,
    rememberScenarioFingerprint,
    setBusy,
    setError,
  };
}
