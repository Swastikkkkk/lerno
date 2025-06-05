import React, { useState } from "react";
import { PlaceholdersAndVanishInput } from "./PlaceholdersAndVanishInput";
import { SparklesCore } from "../ui/sparkles";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { MultiStepLoader } from "@/ui/multi-step-loader";

export default function PlaceholdersAndVanishInputDemo() {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = React.useState("");
  const [isLoading, setIsLoading] = useState(false);

  const placeholders = [
    'I am "audience" teach me this "topic"?',
    "Explain the Pythagorean Theorem with animation",
    'I am "audience"  teach me this "topic"?',
    "Show me how derivatives work with graphs",
    "Give a visual explanation of linear transformations in 3D",
  ];
  const loadingStates = [
    { text: "Finding personalized learning topics..." },
    { text: "Generating educational content..." },
    { text: "Preparing your learning experience..." },
  ];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await axios.post("http://localhost:3001/input-data", {
        data: inputValue,
      });
      console.log(response.data);

      navigate("/learning", {
        state: {
          query: inputValue,
          responseData: response.data.response.data.scenes,
        },
      });
      console.log(response.data.response.data.scenes);
    } catch (error) {
      console.log("The error is " + error);
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
          duration={5000}
          loop={true}
        />
      )}
    </div>
  );
}
