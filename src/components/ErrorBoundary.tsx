import { Component, ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  errorMessage: string;
  stack?: string;
};

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    errorMessage: "",
    stack: undefined,
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || "Unknown rendering error",
    };
  }

  componentDidCatch(error: Error, errorInfo: { componentStack: string }) {
    if (import.meta.env.DEV) {
      console.error("[ErrorBoundary] render crash", error, errorInfo);
    }
    this.setState({ stack: errorInfo.componentStack });
  }

  private reload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen p-4 md:p-8">
        <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
          <Card className="glass-card rounded-2xl border-red-500/40">
            <CardHeader>
              <CardTitle>Something went wrong</CardTitle>
              <CardDescription>
                A rendering error occurred. The app is still running, but this view could not be displayed.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-red-500">{this.state.errorMessage}</p>
              {import.meta.env.DEV && this.state.stack ? (
                <pre className="rounded-lg border border-border p-3 text-xs overflow-auto">
                  {this.state.stack}
                </pre>
              ) : null}
              <Button variant="outline" onClick={this.reload}>
                Reload page
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
