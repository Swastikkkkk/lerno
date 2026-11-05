import React from "react";
import { FaGithub, FaXTwitter, FaLinkedin, FaInstagram } from "react-icons/fa6";

const Footer: React.FC = () => (
  <footer className="bg-black border-t border-[#232323] pt-12 pb-6 px-4 mt-20">
    <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:justify-between gap-12">
      {/* Logo + About */}
      <div className="flex-1 min-w-[200px]">
        <div className="flex items-center mb-4">
          <span className="bg-black rounded-md w-8 h-8 flex items-center justify-center mr-3">
            {/* You can replace this with your SVG/Logo */}
            <span className="text-black font-bold text-xl">
              <img src="logo.png" alt="" />
            </span>
          </span>
          <span className="text-white font-bold text-lg tracking-wide">
            Lerno AI
          </span>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Your AI companion for smarter, adaptive, and interactive learning.
        </p>
        <div className="flex space-x-4 mt-2">
          <a
            href="https://github.com/Swastikkkkk/lerno"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub"
          >
            <FaGithub
              className="text-gray-400 hover:text-white transition"
              size={22}
            />
          </a>
          <a
            href="https://x.com/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="X (Twitter)"
          >
            <FaXTwitter
              className="text-gray-400 hover:text-white transition"
              size={22}
            />
          </a>
          <a
            href="https://linkedin.com/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="LinkedIn"
          >
            <FaLinkedin
              className="text-gray-400 hover:text-white transition"
              size={22}
            />
          </a>
          <a
            href="https://instagram.com/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Instagram"
          >
            <FaInstagram
              className="text-gray-400 hover:text-white transition"
              size={22}
            />
          </a>
        </div>
      </div>

      {/* Footer Links */}
      <div className="flex-1 grid grid-cols-2 md:grid-cols-3 gap-8 text-sm">
        <div>
          <h4 className="text-white font-semibold mb-3">Resources</h4>
          <ul className="space-y-2">
            <li>
              <a
                href="#about"
                className="text-gray-400 hover:text-white transition"
              >
                About
              </a>
            </li>
            <li>
              <a
                href="#features"
                className="text-gray-400 hover:text-white transition"
              >
                Features
              </a>
            </li>
            <li>
              <a
                href="#pricing"
                className="text-gray-400 hover:text-white transition"
              >
                Pricing
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                FAQ
              </a>
            </li>
          </ul>
        </div>
        <div>
          <h4 className="text-white font-semibold mb-3">Community</h4>
          <ul className="space-y-2">
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Blog
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Forum
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Events
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Discord
              </a>
            </li>
          </ul>
        </div>
        <div>
          <h4 className="text-white font-semibold mb-3">Contact</h4>
          <ul className="space-y-2">
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno/issues"
                className="text-gray-400 hover:text-white transition"
              >
                support@lerno.ai
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno/issues"
                className="text-gray-400 hover:text-white transition"
              >
                Contact Form
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Privacy Policy
              </a>
            </li>
            <li>
              <a
                href="https://github.com/Swastikkkkk/lerno"
                className="text-gray-400 hover:text-white transition"
              >
                Terms of Service
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>

    {/* Copyright */}
    <div className="border-t border-[#232323] mt-10 pt-6 text-center text-gray-500 text-xs">
      &copy; {new Date().getFullYear()} Lerno AI. All rights reserved.
    </div>
  </footer>
);

export default Footer;
