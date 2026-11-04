import React, { useState } from "react";
import { PlaceholdersAndVanishInput } from "./PlaceholdersAndVanishInput";
import { SparklesCore } from "../ui/sparkles";
import { useNavigate } from "react-router-dom";
import { generateLesson, getKey, askForKey } from "@/lib/api";
import { MultiStepLoader } from "@/ui/multi-step-loader";

export default function PlaceholdersAndVanishInputDemo() {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = React.useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");

  const placeholders = [
    'I am "audience" teach me this "topic"?',
    "Explain the Pythagorean Theorem with animation",
    'I am "audience"  teach me this "topic"?',
    "Show me how derivatives work with graphs",
    "Give a visual explanation of linear transformations in 3D",
  ];
  const loadingStates = [
    { text: "Planning the lesson" },
    { text: "Writing narration and questions" },
    { text: "Animating each scene with Manim" },
    { text: "Rendering the videos" },
    { text: "Almost there, this takes a minute or two" },
  ];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    if (!getKey()) {
      askForKey("Add a free Gemini key first, then press enter again.");
      return;
    }
    setIsLoading(true);
    setError("");
    setStage("Planning the lesson");

    try {
      const job = await generateLesson(inputValue, (j) => setStage(j.stage));
      navigate("/learning", {
        state: { query: inputValue, topic: job.topic, responseData: job.scenes },
      });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: { message?: string } | string } } })?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : detail?.message;
      setError(msg || (err instanceof Error ? err.message : "Something went wrong. Try again."));
      setIsLoading(false);
    }
  };

  return (
    <div className="h-screen relative w-full bg-black flex flex-col items-center justify-center overflow-hidden rounded-md">
      <div className="w-full absolute inset-0 h-screen">
        <SparklesCore
          id="tsparticlesfullpage"
          background="transparent"
          minSize={0.6}
          maxSize={1.4}
          particleDensity={100}
          className="w-full h-full"
          particleColor="#FFFFFF"
        />
      </div>
      <h2 className="mb-10 text-md text-center sm:text-5xl text-white ">
        What do you want to learn?
      </h2>
      <PlaceholdersAndVanishInput
        placeholders={placeholders}
        onChange={handleChange}
        onSubmit={onSubmit}
      />

      {error && !isLoading && (
        <p className="mt-6 text-sm text-red-300/90 max-w-md text-center">{error}</p>
      )}
      {isLoading && stage && (
        <p className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[110] text-sm text-white/70">{stage}</p>
      )}
      {isLoading && (
        // <div className="mt-6 flex flex-col items-center">
        //   <l-ring-2
        //     size="40"
        //     stroke="5"
        //     stroke-length="0.25"
        //     bg-opacity="0.1"
        //     speed="0.8"
        //     color="white"
        //   ></l-ring-2>
        //   <p className="mt-2 text-white">
        //     Generating your learning experience...
        //   </p>
        // </div>
        <MultiStepLoader
          loadingStates={loadingStates}
          loading={isLoading}
          duration={12000}
          loop={false}
        />
      )}
    </div>
  );
}
