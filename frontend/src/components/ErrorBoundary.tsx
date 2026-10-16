import { Component, type ErrorInfo, type ReactNode } from "react";

/** Shows a friendly recovery card instead of a blank page if a view crashes. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Kawal view crashed", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-red-200 bg-white p-6 text-center">
        <p className="text-lg font-bold text-red-700">Something went wrong on this page.</p>
        <p className="mt-1 text-sm text-slate-600">{this.state.error.message}</p>
        <button onClick={() => window.location.reload()} className="mt-4 rounded-xl bg-brand-900 px-5 py-2.5 font-bold text-white">
          Reload
        </button>
      </div>
    );
  }
}
