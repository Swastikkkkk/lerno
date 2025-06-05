import React, { useState } from "react";

const AceternityNavbar = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <div className="w-full bg-red-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and navigation links - desktop */}
          <div className="flex items-center">
            <div className="text-white font-bold text-xl">LOGO</div>
            <div className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-4">
                <a
                  href="#"
                  className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors duration-300"
                >
                  Home
                </a>
                <a
                  href="#"
                  className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors duration-300"
                >
                  About
                </a>
                <a
                  href="#"
                  className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors duration-300"
                >
                  Features
                </a>
              </div>
            </div>
          </div>

          {/* Buttons - desktop */}
          <div className="hidden md:flex items-center space-x-4">
            <button className="text-white bg-transparent border border-gray-600 hover:border-white px-4 py-2 rounded-md text-sm font-medium transition-all duration-300">
              Login
            </button>
            <button className="text-black bg-white hover:bg-gray-200 px-4 py-2 rounded-md text-sm font-medium transition-colors duration-300">
              Sign up
            </button>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white focus:outline-none"
            >
              <svg
                className="h-6 w-6"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                {isMenuOpen ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {isMenuOpen && (
        <div className="md:hidden bg-black border-t border-gray-800">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
            <a
              href="#"
              className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
            >
              Home
            </a>
            <a
              href="#"
              className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
            >
              About
            </a>
            <a
              href="#"
              className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
            >
              Features
            </a>
          </div>
          <div className="px-2 pt-2 pb-3 space-y-3">
            <button className="w-full text-white bg-transparent border border-gray-600 hover:border-white px-4 py-2 rounded-md text-sm font-medium transition-all duration-300">
              Login
            </button>
            <button className="w-full text-black bg-white hover:bg-gray-200 px-4 py-2 rounded-md text-sm font-medium transition-colors duration-300">
              Sign up
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AceternityNavbar;
