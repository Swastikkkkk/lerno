import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import {
  createBrowserRouter,
  createRoutesFromElements,
  Route,
  RouterProvider,
  Routes,
} from "react-router-dom";
import PlaceholdersAndVanishInputDemo from "./components/PlaceholdersAndVanishInputDemo.tsx";
import "./App.css";
import LearningPage from "./components/LearningPage.tsx";
import LandingPage from "./components/LandingPage.tsx";

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route path="/">
      <Route path="" element={<LandingPage />} />
      <Route path="/chat" element={<PlaceholdersAndVanishInputDemo />} />
      <Route path="/learning" element={<LearningPage />} />
    </Route>
  )
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* <App /> */}
    <RouterProvider router={router} />
  </StrictMode>
);
