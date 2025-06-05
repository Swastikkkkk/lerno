import { ComponentPropsWithoutRef, CSSProperties, FC } from "react";

import { cn } from "@/lib/utils";

export interface AnimatedShinyTextProps
  extends ComponentPropsWithoutRef<"span"> {
  shimmerWidth?: number;
}

export const AnimatedShinyText: FC<AnimatedShinyTextProps> = ({
  children,
  className,
  shimmerWidth = 200,
  ...props
}) => {
  return (
    <span
      style={
        {
          "--shiny-width": `${shimmerWidth}px`,
        } as CSSProperties
      }
      className={cn(
        "mx-auto max-w-md text-transparent bg-clip-text",

        // Shine effect
        "animate-shiny-text bg-[size:200%_100%]",

        // Shine gradient
        "bg-gradient-to-r from-neutral-400/70 via-white/90 to-neutral-400/70",

        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
