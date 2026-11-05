"use client";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function AceternityNavbar() {
  const navItems = [
    { name: "Home", link: "#home" },
    { name: "About", link: "#about" },
    { name: "Features", link: "#features" },
    { name: "Pricing", link: "#pricing" },
  ];

  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navigate = useNavigate();
  // no accounts yet: both buttons take you straight to the lesson builder
  const handleLogin = () => navigate("/chat");
  const handleSignup = () => navigate("/chat");

  return (
    <div className="relative">
      {/* Custom Animations Style */}
      <style>{`
        @keyframes slideInUp {
          0% {
            opacity: 0;
            transform: translateY(20px);
          }
          100% {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        /* Ensure backdrop-filter support */
        .glass-effect {
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
        }
        
        .glass-effect-light {
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
        }
      `}</style>

      {/* Main Floating Navbar */}
      <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-[9999] w-[96%] sm:w-[90%] md:w-[85%] lg:w-[80%] xl:w-[75%] max-w-6xl">
        <div
          className={`
            relative overflow-hidden rounded-xl sm:rounded-2xl border transition-all duration-500 ease-out glass-effect
            ${
              isScrolled
                ? "bg-black/95 border-gray-800/50 shadow-2xl shadow-black/40"
                : "bg-black/90 border-gray-800/30 shadow-xl shadow-black/20"
            }
          `}
          style={{
            background: isScrolled
              ? "rgba(0, 0, 0, 0.95)"
              : "rgba(0, 0, 0, 0.90)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
          }}
        >
          {/* Gradient overlay for extra depth */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.02) 50%, transparent 100%)",
            }}
          ></div>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center justify-between w-full px-4 sm:px-6 py-3 sm:py-4 bg-transparent relative z-10">
            <div className="flex-shrink-0 relative z-10">
              <a
                href="#"
                className="flex items-center space-x-2 px-2 py-1 text-sm font-normal"
              >
                <img
                  src="/logo.png"
                  alt="logo"
                  width={24}
                  height={24}
                  className=" sm:w-[30px] sm:h-[30px]"
                />
                <span className="font-medium text-white text-sm sm:text-base">
                  Lerno AI
                </span>
              </a>
            </div>

            <div className="flex items-center space-x-4 sm:space-x-6 lg:space-x-8">
              {navItems.map((item) => (
                <a
                  key={item.link}
                  href={item.link}
                  className="relative text-white/90 hover:text-white font-medium text-sm tracking-wide transition-all duration-300 group whitespace-nowrap"
                >
                  {item.name}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-white transition-all duration-300 group-hover:w-full rounded-full"></span>
                </a>
              ))}
            </div>

            <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
              <button
                onClick={handleLogin}
                className="px-3 cursor-pointer sm:px-4 py-2 text-xs sm:text-sm font-medium text-white/90 bg-black/50 border border-gray-700/50 hover:border-gray-600 hover:bg-gray-900/50 hover:text-white rounded-lg sm:rounded-xl transition-all duration-300 glass-effect-light hover:shadow-lg whitespace-nowrap"
              >
                Login
              </button>
              <button
                onClick={handleSignup}
                className="px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium bg-white text-black hover:bg-gray-100 rounded-lg sm:rounded-xl shadow-lg hover:shadow-xl transition-all duration-300  border border-gray-200 whitespace-nowrap cursor-pointer"
              >
                Sign up
              </button>
            </div>
          </div>

          {/* Tablet Navigation (768px - 1023px) */}
          <div className="hidden md:flex lg:hidden items-center justify-between w-full px-4 sm:px-6 py-3 sm:py-4 bg-transparent relative z-10">
            <div className="flex-shrink-0 relative z-10">
              <a
                href="#"
                className="flex items-center space-x-2 px-2 py-1 text-sm font-normal"
              >
                <img
                  src="https://assets.aceternity.com/logo-dark.png"
                  alt="logo"
                  width={28}
                  height={28}
                  className="invert"
                />
                <span className="font-medium text-white text-sm">Lerno AI</span>
              </a>
            </div>

            <div className="flex items-center space-x-4">
              {navItems.map((item) => (
                <a
                  key={item.link}
                  href={item.link}
                  className="relative text-white/90 hover:text-white font-medium text-sm tracking-wide transition-all duration-300 group"
                >
                  {item.name}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-white transition-all duration-300 group-hover:w-full rounded-full"></span>
                </a>
              ))}
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={handleLogin}
                className="px-3 cursor-pointer py-2 text-xs font-medium text-white/90 bg-black/50 border border-gray-700/50 hover:border-gray-600 hover:bg-gray-900/50 hover:text-white rounded-lg transition-all duration-300 glass-effect-light hover:shadow-lg "
              >
                Login
              </button>
              <button
                onClick={handleSignup}
                className="px-3 py-2 text-xs font-medium bg-white text-black hover:bg-gray-100 rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 border border-gray-200 cursor-pointer"
              >
                Sign up
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          <div className="md:hidden">
            <div className="flex items-center justify-between w-full px-4 py-3 bg-transparent">
              <div className="flex-shrink-0">
                <a
                  href="#"
                  className="flex items-center space-x-2 px-1 py-1 text-sm font-normal"
                >
                  <img
                    src="https://assets.aceternity.com/logo-dark.png"
                    alt="logo"
                    width={24}
                    height={24}
                    className="invert"
                  />
                  <span className="font-medium text-white text-sm">
                    Lerno AI
                  </span>
                </a>
              </div>
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="h-8 w-8 text-white/90 hover:text-white transition-colors duration-300 flex items-center justify-center"
              >
                {isMobileMenuOpen ? (
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 6h16M4 12h16M4 18h16"
                    />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 z-[9998] md:hidden glass-effect-light"
            onClick={() => setIsMobileMenuOpen(false)}
          ></div>

          {/* Mobile Menu */}
          <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-[9999] w-[92%] max-w-sm md:hidden">
            <div
              className="border border-gray-800/50 rounded-xl shadow-2xl shadow-black/50 p-4 sm:p-6 overflow-hidden glass-effect"
              style={{
                background: "rgba(0, 0, 0, 0.95)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
              }}
            >
              {/* Gradient overlay */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(255,255,255,0.03) 0%, transparent 100%)",
                }}
              ></div>

              <div className="relative space-y-1">
                {navItems.map((item, index) => (
                  <a
                    key={item.link}
                    href={item.link}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="block text-white/90 hover:text-white font-medium py-3 px-3 rounded-xl hover:bg-gray-800/50 transition-all duration-300 border border-transparent hover:border-gray-700/50 text-sm"
                    style={{
                      animation: `slideInUp 0.4s ease-out ${index * 0.1}s both`,
                    }}
                  >
                    {item.name}
                  </a>
                ))}
              </div>

              <div className="relative flex flex-col gap-2 mt-4 pt-4 border-t border-gray-800/50">
                <button
                  onClick={() => {
                    handleLogin();
                    setIsMobileMenuOpen(false);
                  }}
                  className="w-full cursor-pointer py-3 text-sm font-medium text-white/90 bg-black/50 border border-gray-700/50 hover:border-gray-600 hover:bg-gray-900/50 hover:text-white rounded-xl transition-all duration-300"
                >
                  Login
                </button>
                <button
                  onClick={() => {
                    handleSignup();
                    setIsMobileMenuOpen(false);
                  }}
                  className="w-full py-3 text-sm font-medium bg-white text-black hover:bg-gray-100 rounded-xl shadow-lg transition-all duration-300 border border-gray-200 cursor-pointer"
                >
                  Sign up
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
