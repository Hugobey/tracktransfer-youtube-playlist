import type { ButtonHTMLAttributes, ReactNode } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
  children: ReactNode;
};

const styles = {
  primary: "bg-blue text-white hover:bg-blue-2 disabled:bg-blue/40",
  secondary: "border border-line-strong bg-transparent text-ink hover:border-blue disabled:opacity-40",
  quiet: "bg-transparent text-muted hover:text-ink disabled:opacity-40",
};

export function Button({ variant = "primary", className = "", children, type = "button", ...props }: Props) {
  return (
    <button
      type={type}
      className={`inline-flex h-9 items-center justify-center px-3.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
