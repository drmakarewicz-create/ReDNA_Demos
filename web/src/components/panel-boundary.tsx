'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';

import { PanelError } from './panel-error';

interface PanelBoundaryProps {
  children: ReactNode;
  resetKeys?: ReadonlyArray<unknown>;
  title?: string;
  onRetry?: () => void;
}

interface PanelBoundaryState {
  hasError: boolean;
  message: string | null;
}

export class PanelBoundary extends Component<PanelBoundaryProps, PanelBoundaryState> {
  state: PanelBoundaryState = {
    hasError: false,
    message: null
  };

  static getDerivedStateFromError(error: Error): PanelBoundaryState {
    return { hasError: true, message: error?.message ?? 'Something went wrong.' };
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('PanelBoundary caught error', error);
  }

  componentDidUpdate(prevProps: PanelBoundaryProps) {
    if (this.state.hasError) {
      const { resetKeys = [] } = this.props;
      const { resetKeys: prevReset = [] } = prevProps;
      if (resetKeys.length !== prevReset.length || resetKeys.some((value, index) => value !== prevReset[index])) {
        this.reset();
      }
    }
  }

  reset() {
    this.setState({ hasError: false, message: null });
  }

  render() {
    if (this.state.hasError) {
      const message = this.state.message ?? 'Something went wrong.';
      return (
        <div className="rounded-2xl border border-rose-500/50 bg-rose-500/10 p-4">
          <PanelError
            message={message}
            onRetry={() => {
              this.reset();
              this.props.onRetry?.();
            }}
          />
        </div>
      );
    }
    return this.props.children;
  }
}
