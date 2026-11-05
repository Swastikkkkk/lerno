import React, { useState, useEffect, useRef } from "react";
import AIChatbot from "./AIChatbot";
import { HoverBorderGradient } from "@/ui/hover-border-gradient";
import { AnimatedShinyText } from "@/ui/animated-shiny-text";
import { cn } from "@/lib/utils";
import { useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { mediaUrl, speak, stopSpeaking, translate, getLang, LANG_EVENT, type Scene } from "@/lib/api";
import LanguagePicker from "./LanguagePicker";
import LessonPlayer from "./LessonPlayer";

const LearningPage = () => {
  const location = useLocation();
  const [murfError] = useState<string | null>(null);

  const FetchData: Scene[] = location.state?.responseData || [
    {
      scene_number: 1,
      video_url: null,
      title: "Introduction to Vectors",
      assessment: {
        multiple_choice: {
          question: "What is the primary purpose of vectors in computing?",
          choices: [
            "A. Data storage only",
            "B. Mathematical operations and graphics",
            "C. Text processing",
            "D. Audio manipulation",
          ],
          correct_index: 1,
        },
      },
      narration:
        "Vectors are a fundamental concept in computing, especially in graphics programming and mathematical operations.",
    },
  ];

  const [selectedAnswerIndex, setSelectedAnswerIndex] = useState<number | null>(
    null
  );
  const [hasAnswered, setHasAnswered] = useState(false);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  const currentSlide = FetchData[currentSlideIndex] || FetchData[0];
  const [lang, setLangState] = useState(getLang());
  useEffect(() => {
    const on = (e: Event) => setLangState((e as CustomEvent<string>).detail);
    window.addEventListener(LANG_EVENT, on);
    return () => window.removeEventListener(LANG_EVENT, on);
  }, []);

  // Text for the current slide in the chosen language (Murf translate, English passes through).
  const mc = currentSlide.assessment.multiple_choice;
  const [shown, setShown] = useState({ key: "", title: currentSlide.title, narration: currentSlide.narration, question: mc.question, choices: mc.choices });
  const slideKey = `${lang}|${currentSlideIndex}|${currentSlide.title}`;
  useEffect(() => {
    let live = true;
    const src = [currentSlide.title, currentSlide.narration, mc.question, ...mc.choices];
    translate(src, lang).then((t) => {
      if (live) setShown({ key: slideKey, title: t[0], narration: t[1], question: t[2], choices: t.slice(3) });
    });
    return () => { live = false; };
  }, [slideKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const answer = shown.choices;
  const question = shown.question;
  const correctAnswerIndex =
    currentSlide.assessment.multiple_choice.correct_index;

  function handleAnswerClick(currIndex: number) {
    setSelectedAnswerIndex(currIndex);
    setHasAnswered(true);
  }

  function handleNextSlide() {
    const totalSlides = Math.min(FetchData.length, 5);
    if (currentSlideIndex < totalSlides - 1) {
      setCurrentSlideIndex((prevIndex) => prevIndex + 1);
    } else {
      setCurrentSlideIndex(0);
    }

    setSelectedAnswerIndex(null);
    setHasAnswered(false);
  }

  const slideVariants = {
    hidden: (direction: number) => ({
      x: direction > 0 ? 300 : -300,
      opacity: 0,
    }),
    visible: {
      x: 0,
      opacity: 1,
      transition: {
        type: "spring",
        stiffness: 300,
        damping: 30,
      },
    },
    exit: (direction: number) => ({
      x: direction > 0 ? -300 : 300,
      opacity: 0,
      transition: {
        duration: 0.2,
      },
    }),
  };

  const [direction, setDirection] = useState(1);

  function animatedNextSlide() {
    setDirection(1);
    handleNextSlide();
  }

  const [narration, setNarration] = useState<HTMLAudioElement | null>(null);
  // Narration: Murf through the backend, browser voice as a fallback.
  useEffect(() => {
    const signal = { cancelled: false };
    let audio: HTMLAudioElement | null = null;
    setNarration(null);
    if (shown.key === slideKey && shown.narration) {
      speak(shown.narration, signal, lang).then((a) => {
        if (signal.cancelled) stopSpeaking(a);
        else { audio = a; setNarration(a); }
      });
    }
    return () => {
      signal.cancelled = true;
      stopSpeaking(audio);
    };
  }, [shown.key, shown.narration]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col items-center w-full min-h-screen md:h-screen md:overflow-hidden bg-black p-4 md:p-6">
      <div className="z-10 flex items-center gap-3 mb-4 md:mb-5 shrink-0 w-full max-w-6xl justify-center relative">
        <div
          className={cn(
            "group rounded-full border border-black/5 bg-neutral-900 text-base transition-all ease-in hover:cursor-pointer hover:bg-neutral-800 shadow-lg"
          )}
        >
          <AnimatedShinyText className="inline-flex items-center justify-center px-6 py-2.5 font-medium text-lg transition ease-out">
            <AnimatePresence mode="wait">
              <motion.span
                key={currentSlideIndex}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                {shown.title}
              </motion.span>
            </AnimatePresence>
          </AnimatedShinyText>
        </div>
        <LanguagePicker className="md:absolute md:right-0" />
      </div>
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentSlideIndex}
          custom={direction}
          variants={slideVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="grid grid-cols-1 md:grid-cols-3 md:grid-rows-[minmax(0,3fr)_minmax(0,2fr)] gap-4 md:gap-5 w-full max-w-6xl md:flex-1 md:min-h-0"
        >
          {/* Box 1: Video */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 md:col-span-2 h-72 md:h-full md:min-h-0 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">

            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="h-full w-full flex items-center justify-center p-2">
              <LessonPlayer
                src={mediaUrl(currentSlide.video_url)}
                audio={narration}
                captions={shown.narration}
                emptyText={location.state?.responseData
                  ? "This scene's animation couldn't be rendered, but the narration and quiz still work."
                  : "Start from the home page to generate a lesson."}
              />
            </div>
            <div className="absolute inset-0 pointer-events-none border border-white/5 rounded-xl"></div>
          </div>

          {/* Narration Box */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 p-6 h-72 md:h-full md:min-h-0 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
            <div className="absolute inset-0 bg-gradient-to-br from-green-500/20 via-emerald-500/20 to-teal-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="relative z-10 h-full flex flex-col">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-4 h-4"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-white">Narration</h3>
              </div>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="flex-grow overflow-y-auto pr-2 text-white/70 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
              >
                <p>{shown.narration}</p>
                {murfError && (
                  <div style={{ color: "#F87171", marginTop: "8px" }}>
                    {murfError}
                  </div>
                )}
              </motion.div>
              <div className="pt-4 flex justify-end shrink-0">
              <HoverBorderGradient
                containerClassName={`rounded-full ${
                  !hasAnswered && "opacity-50 pointer-events-none"
                }`}
                as="button"
                className="bg-black text-white flex items-center space-x-2 px-6 py-3"
                onClick={animatedNextSlide}
              >
                <span>Next Lesson</span>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-5 h-5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
                  />
                </svg>
              </HoverBorderGradient>
              </div>
            </div>
            <div className="absolute -inset-px bg-gradient-to-r from-green-500/30 via-transparent to-emerald-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
          </div>
          {/* Box 2: MCQ Question & Answers */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 md:col-span-2 p-5 min-h-[18rem] md:min-h-0 md:h-full bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 via-purple-500/20 to-cyan-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="relative z-10 flex flex-col h-full">
              <h3 className="text-lg font-medium text-white mb-2">Question</h3>
              <p className="text-white/80 mb-4">{question}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 content-start flex-grow min-h-0 overflow-y-auto pr-1">
                {answer.map((info: string, index: number) => (
                  <motion.button
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.3,
                      delay: index * 0.1,
                    }}
                    className={`w-full h-full text-left px-4 py-3 text-sm rounded-lg border ${
                      selectedAnswerIndex === index &&
                      correctAnswerIndex === index
                        ? "bg-green-500/30 border-green-500/50 text-white"
                        : selectedAnswerIndex === index
                        ? "bg-red-500/30 border-red-500/50 text-white"
                        : "bg-white/5 border-white/10 text-white/70 hover:bg-white/10 hover:border-white/20"
                    } transition-all duration-200 ${
                      hasAnswered && "cursor-default"
                    }`}
                    onClick={() => !hasAnswered && handleAnswerClick(index)}
                    key={index}
                    disabled={hasAnswered}
                  >
                    {info}
                  </motion.button>
                ))}
              </div>
            </div>
            <div className="absolute -inset-px bg-gradient-to-r from-blue-500/30 via-transparent to-purple-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
          </div>
          {/* Box 3: AI Chatbot */}
          <div className="md:col-span-1 h-96 md:h-full md:min-h-0">
            <AIChatbot
              lessonTitle={currentSlide.title}
              lessonContent={currentSlide.narration}
              currentQuestion={mc.question}
            />
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
};

export default LearningPage;
