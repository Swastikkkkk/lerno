import React, { useState, useEffect, useRef } from "react";
import AIChatbot from "./AIChatbot";
import { HoverBorderGradient } from "@/ui/hover-border-gradient";
import { AnimatedShinyText } from "@/ui/animated-shiny-text";
import { cn } from "@/lib/utils";
import { useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { getStorage, ref, getDownloadURL, listAll } from "firebase/storage";
import { initializeApp } from "firebase/app";
import axios from "axios";

const firebaseConfig = {
  apiKey: "AIzaSyBhIvBxbGblvV_2Wr4UQ3PyaehwvWi6H3w",
  authDomain: "lerno-cd286.firebaseapp.com",
  projectId: "lerno-cd286",
  storageBucket: "lerno-cd286.firebasestorage.app",
  messagingSenderId: "995948277315",
  appId: "1:995948277315:web:340963bb717be5da436ef6",
};
const app = initializeApp(firebaseConfig);

const MURF_API_KEY = "ap2_4fda0ed0-fbb8-42d8-8342-0ad8b064361c";

const LearningPage = () => {
  const location = useLocation();
  const [videoURLs, setVideoURLs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // For Murf direct audio playback
  const murfAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isMurfLoading, setIsMurfLoading] = useState(false);
  const [murfError, setMurfError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        setLoading(true);
        const storage = getStorage(app);
        const storageRef = ref(storage, "/");
        const result = await listAll(storageRef);
        const videoRefs = result.items.filter((item) =>
          item.name.toLowerCase().endsWith(".mp4")
        );
        videoRefs.sort((a, b) => {
          const sceneA = a.name.match(/_Scene(\d+)\.mp4$/i);
          const sceneB = b.name.match(/_Scene(\d+)\.mp4$/i);
          if (sceneA && sceneB) {
            return parseInt(sceneA[1]) - parseInt(sceneB[1]);
          }
          return a.name.localeCompare(b.name);
        });
        const urls = await Promise.all(
          videoRefs.map((videoRef) => getDownloadURL(videoRef))
        );
        setVideoURLs(urls);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching videos:", error);
        setLoading(false);
      }
    };
    fetchVideos();
  }, []);

  const FetchData = location.state?.responseData || [
    {
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
  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);

  const currentSlide = FetchData[currentSlideIndex] || FetchData[0];
  const answer = currentSlide.assessment.multiple_choice.choices;
  const question = currentSlide.assessment.multiple_choice.question;
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

    if (videoURLs.length > 0) {
      if (currentVideoIndex < videoURLs.length - 1) {
        setCurrentVideoIndex((prevIndex) => prevIndex + 1);
      } else {
        setCurrentVideoIndex(0);
      }
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

  // --- Murf Autoplay Handler (Strict Cleanup, No Double Audio) ---
  useEffect(() => {
    let cancelled = false;
    let audio: HTMLAudioElement | null = null;

    async function fetchAndPlayMurfAudio() {
      setIsMurfLoading(true);
      setMurfError(null);

      // Immediately stop and clear any previous audio
      if (murfAudioRef.current) {
        murfAudioRef.current.pause();
        murfAudioRef.current.currentTime = 0;
        murfAudioRef.current = null;
      }

      try {
        const response = await axios.post(
          "https://api.murf.ai/v1/speech/generate",
          {
            text: currentSlide.narration,
            voiceId: "en-US-natalie",
            format: "mp3",
            channelType: "MONO",
            sampleRate: 44100,
          },
          {
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
              "api-key": MURF_API_KEY,
            },
          }
        );

        if (cancelled) return;

        const audioUrl = response.data.audioFile;
        if (audioUrl) {
          audio = new Audio(audioUrl);
          murfAudioRef.current = audio;

          const playPromise = audio.play();
          playPromise?.catch(() => {
            // If autoplay is blocked, play on first user interaction
            const handleUserInteraction = () => {
              audio && audio.play();
              window.removeEventListener("click", handleUserInteraction);
              window.removeEventListener("keydown", handleUserInteraction);
            };
            window.addEventListener("click", handleUserInteraction, {
              once: true,
            });
            window.addEventListener("keydown", handleUserInteraction, {
              once: true,
            });
          });
        }
      } catch (e) {
        if (!cancelled) {
          setMurfError(
            "Failed to fetch narration audio from Murf. See console for details."
          );
          console.error(e);
        }
      }
      if (!cancelled) setIsMurfLoading(false);
    }

    if (currentSlide.narration) fetchAndPlayMurfAudio();

    return () => {
      cancelled = true;
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
      if (murfAudioRef.current) {
        murfAudioRef.current.pause();
        murfAudioRef.current.currentTime = 0;
        murfAudioRef.current = null;
      }
    };
  }, [currentSlide.narration]);

  return (
    <div className="flex flex-col items-center justify-center w-full min-h-screen bg-black p-4 md:p-8">
      <div className="z-10 flex mb-8">
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
                {currentSlide.title}
              </motion.span>
            </AnimatePresence>
          </AnimatedShinyText>
        </div>
      </div>
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentSlideIndex}
          custom={direction}
          variants={slideVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 w-full max-w-6xl"
        >
          {/* Box 1: Video */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 md:col-span-2 h-72 md:h-96 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 via-purple-500/20 to-pink-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="h-full w-full flex items-center justify-center p-2">
              {loading ? (
                <div className="text-white/70 flex flex-col items-center">
                  <svg
                    className="animate-spin h-10 w-10 text-white/30 mb-3"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  <span>Loading videos...</span>
                </div>
              ) : videoURLs.length > 0 ? (
                <div className="w-auto h-auto">
                  <video
                    src={videoURLs[currentVideoIndex]}
                    autoPlay
                    muted
                    loop
                    className="object-contain rounded-lg"
                    key={videoURLs[currentVideoIndex]}
                  ></video>
                </div>
              ) : (
                <div className="text-white/70">No videos found in storage</div>
              )}
            </div>
            <div className="absolute inset-0 pointer-events-none border border-white/5 rounded-xl"></div>
            <div className="absolute -inset-px bg-gradient-to-r from-purple-500/30 via-transparent to-cyan-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
          </div>

          {/* Narration Box */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 p-6 h-72 md:h-96 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
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
                <p>{currentSlide.narration}</p>
                {murfError && (
                  <div style={{ color: "#F87171", marginTop: "8px" }}>
                    {murfError}
                  </div>
                )}
              </motion.div>
            </div>
            <div className="absolute -inset-px bg-gradient-to-r from-green-500/30 via-transparent to-emerald-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
          </div>
          {/* Box 2: MCQ Question & Answers */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 p-4 min-h-[18rem] h-auto bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 via-purple-500/20 to-cyan-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="relative z-10 flex flex-col h-full">
              <h3 className="text-xl font-medium text-white mb-3">Question</h3>
              <p className="text-white/70 mb-4">{question}</p>
              <div className="space-y-3 flex-grow">
                {answer.map((info: string, index: number) => (
                  <motion.button
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.3,
                      delay: index * 0.1,
                    }}
                    className={`w-full text-left px-4 py-2.5 rounded-lg border ${
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
          <div className="md:col-span-1 h-full">
            <AIChatbot
              lessonTitle={currentSlide.title}
              lessonContent={currentSlide.narration}
              currentQuestion={currentSlide.assessment.multiple_choice.question}
            />
          </div>
          {/* Box 4: Next button */}
          <div className="relative group overflow-hidden rounded-xl border border-white/10 p-6 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70">
            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/20 via-orange-500/20 to-rose-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>
            <div className="h-full w-full flex items-center justify-center relative z-10">
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
            <div className="absolute -inset-px bg-gradient-to-r from-amber-500/30 via-transparent to-rose-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
};

export default LearningPage;
