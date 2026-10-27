import { useEffect, useState } from "react";

export type Load<T> = { status: "loading" } | { status: "ready"; data: T } | { status: "failed"; message: string };

// Fetches on mount and whenever deps change; ignores responses that arrive after a newer request.
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[]): Load<T> {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    fetcher()
      .then((data) => live && setState({ status: "ready", data }))
      .catch((err: Error) => live && setState({ status: "failed", message: err.message }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
