"use client";

import { useCallback } from "react";
import Particles from "react-tsparticles";
import { Engine } from "tsparticles-engine";
import { loadSlim } from "tsparticles-slim";

export function SparklesCore({
  id,
  background,
  minSize,
  maxSize,
  particleDensity,
  className,
  particleColor,
}: {
  id: string;
  background?: string;
  minSize?: number;
  maxSize?: number;
  particleDensity?: number;
  className?: string;
  particleColor?: string;
}) {
  const particlesInit = useCallback(async (engine: Engine) => {
    await loadSlim(engine);
  }, []);

  return (
    <Particles
      id={id}
      init={particlesInit}
      options={{
        background: {
          color: {
            value: background || "transparent",
          },
        },
        particles: {
          color: {
            value: particleColor || "#ffffff",
          },
          number: {
            value: particleDensity || 100,
            density: {
              enable: true,
              value_area: 800,
            },
          },
          size: {
            value: { min: minSize || 0.6, max: maxSize || 1.4 },
          },
          move: {
            enable: true,
            speed: 0.5,
          },
        },
      }}
      className={className}
    />
  );
}
