import type { ProjectMasterWorkpoint } from "../../contracts";

export type ProjectMasterDisplayIdentity = {
  projectDataVersionId: string;
  workpointIds: string[];
  requestKey: string;
};

type ProjectMasterDisplayStateBase = {
  identity: ProjectMasterDisplayIdentity;
  generation: number;
};

export type ProjectMasterDisplayLoadingState = ProjectMasterDisplayStateBase & {
  status: "loading";
};

export type ProjectMasterDisplayReadyState = ProjectMasterDisplayStateBase & {
  status: "ready";
  workpoints: ProjectMasterWorkpoint[];
};

export type ProjectMasterDisplayErrorState = ProjectMasterDisplayStateBase & {
  status: "error";
  message: string;
};

export type ProjectMasterDisplayState =
  | ProjectMasterDisplayLoadingState
  | ProjectMasterDisplayReadyState
  | ProjectMasterDisplayErrorState;

export type ProjectMasterWorkpointLoader = (
  projectDataVersionId: string,
  workpointId: string,
) => Promise<ProjectMasterWorkpoint>;

export type ProjectMasterDisplayCoordinator = {
  getState: () => ProjectMasterDisplayState | null;
  retry: () => Promise<void>;
  setIdentity: (projectDataVersionId: string, workpointIds: string[]) => Promise<void>;
  subscribe: (listener: (state: ProjectMasterDisplayState) => void) => () => void;
  dispose: () => void;
};

const genericLoadErrorMessage = "权威项目主数据映射加载失败，请重试。";

export function createProjectMasterDisplayIdentity(
  projectDataVersionId: string,
  workpointIds: string[],
): ProjectMasterDisplayIdentity {
  const normalizedIds = Array.from(new Set(
    workpointIds.filter((workpointId) => typeof workpointId === "string" && workpointId.length > 0),
  )).sort();
  return {
    projectDataVersionId,
    workpointIds: normalizedIds,
    requestKey: JSON.stringify([projectDataVersionId, normalizedIds]),
  };
}

export function createProjectMasterDisplayCoordinator(
  loadWorkpoint: ProjectMasterWorkpointLoader,
): ProjectMasterDisplayCoordinator {
  const listeners = new Set<(state: ProjectMasterDisplayState) => void>();
  const readyCache = new Map<string, ProjectMasterWorkpoint[]>();
  let currentIdentity: ProjectMasterDisplayIdentity | null = null;
  let currentState: ProjectMasterDisplayState | null = null;
  let currentToken: string | null = null;
  let activePromise: Promise<void> | null = null;
  let generation = 0;
  let disposed = false;

  function publish(state: ProjectMasterDisplayState): void {
    if (disposed) return;
    currentState = state;
    for (const listener of listeners) listener(state);
  }

  function isCurrent(identity: ProjectMasterDisplayIdentity, token: string): boolean {
    return !disposed
      && currentIdentity?.requestKey === identity.requestKey
      && currentToken === token;
  }

  function start(identity: ProjectMasterDisplayIdentity): Promise<void> {
    generation += 1;
    const requestGeneration = generation;
    const token = `${identity.requestKey}:${requestGeneration}`;
    currentToken = token;
    publish({ status: "loading", identity, generation: requestGeneration });

    const request = Promise.all(
      identity.workpointIds.map((workpointId) => loadWorkpoint(identity.projectDataVersionId, workpointId)),
    ).then(
      (workpoints) => {
        const completeWorkpoints = [...workpoints];
        readyCache.set(identity.requestKey, completeWorkpoints);
        if (!isCurrent(identity, token)) return;
        publish({
          status: "ready",
          identity,
          generation: requestGeneration,
          workpoints: completeWorkpoints,
        });
      },
      () => {
        if (!isCurrent(identity, token)) return;
        publish({
          status: "error",
          identity,
          generation: requestGeneration,
          message: genericLoadErrorMessage,
        });
      },
    );
    activePromise = request;
    return request;
  }

  async function setIdentity(projectDataVersionId: string, workpointIds: string[]): Promise<void> {
    if (disposed) return;
    const identity = createProjectMasterDisplayIdentity(projectDataVersionId, workpointIds);
    if (currentIdentity?.requestKey === identity.requestKey) {
      if (currentState?.status === "loading" && activePromise) await activePromise;
      return;
    }

    currentIdentity = identity;
    currentToken = null;
    const cached = readyCache.get(identity.requestKey);
    if (cached) {
      publish({ status: "ready", identity, generation, workpoints: [...cached] });
      return;
    }
    if (identity.workpointIds.length === 0) {
      readyCache.set(identity.requestKey, []);
      publish({ status: "ready", identity, generation, workpoints: [] });
      return;
    }
    await start(identity);
  }

  async function retry(): Promise<void> {
    if (disposed || !currentIdentity) return;
    readyCache.delete(currentIdentity.requestKey);
    await start(currentIdentity);
  }

  return {
    getState: () => currentState,
    retry,
    setIdentity,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    dispose() {
      disposed = true;
      currentToken = null;
      listeners.clear();
    },
  };
}
