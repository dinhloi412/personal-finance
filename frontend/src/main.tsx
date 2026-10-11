/**
 * The entry point.
 *
 * An error boundary is here rather than deeper in the tree because the one
 * failure a personal-data app must never have is a blank page: if a view
 * throws, the user needs to be told that nothing was lost and where the data
 * actually lives.
 */

import { Component, StrictMode } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./index.css";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("SoTaiSan failed to render", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-xl p-6">
          <h1 className="text-lg font-semibold">SoTaiSan · Sổ Tài Sản</h1>
          <p className="mt-2 text-sm text-slate-600">
            The interface failed to render. Your data is untouched: it is the
            SQLite file <code>backend/data.db</code>.
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-rose-50 p-3 text-xs text-rose-700">
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={() => globalThis.location.reload()}
            className="mt-4 rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const container = document.getElementById("root");
if (container === null) {
  throw new Error("#root is missing from index.html");
}

createRoot(container).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
