import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, createRoutesFromElements, Route, RouterProvider } from "react-router-dom";
import "./App.css";
import PlaceholdersAndVanishInputDemo from "./components/PlaceholdersAndVanishInputDemo.tsx";
import LearningPage from "./components/LearningPage.tsx";
import LandingPage from "./components/LandingPage.tsx";
import AuthPage from "./components/AuthPage.tsx";
import { AppShell } from "./components/Sidebar.tsx";
import { AuthProvider } from "./lib/auth.tsx";

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route path="/">
      <Route path="" element={<LandingPage />} />
      <Route path="login" element={<AuthPage mode="login" />} />
      <Route path="signup" element={<AuthPage mode="signup" />} />
      <Route path="chat" element={<AppShell><PlaceholdersAndVanishInputDemo /></AppShell>} />
      <Route path="learning" element={<AppShell><LearningPage /></AppShell>} />
    </Route>
  )
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </StrictMode>
);
