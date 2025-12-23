"use client";

import { useEffect, useRef, useState } from "react";

type LazyVideoProps = {
  src: string;
  className?: string;
  poster?: string;
  autoPlay?: boolean;
  loop?: boolean;
  muted?: boolean;
  playsInline?: boolean;
  isActive?: boolean;
};

export function LazyVideo({
  src,
  className = "",
  poster,
  autoPlay = true,
  loop = true,
  muted = true,
  playsInline = true,
  isActive = true,
}: LazyVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const element = videoRef.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setShouldLoad(true);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.25, rootMargin: "200px" }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Handle loading and ready state
  useEffect(() => {
    if (!shouldLoad || !videoRef.current) return;

    const video = videoRef.current;

    // If src changed, we are not ready
    setIsReady(false);

    const handleReady = () => setIsReady(true);
    // If we already have data, we might be ready
    if (video.readyState >= 3) {
      setIsReady(true);
    }

    video.addEventListener("loadeddata", handleReady);
    video.addEventListener("canplay", handleReady);

    return () => {
      video.removeEventListener("loadeddata", handleReady);
      video.removeEventListener("canplay", handleReady);
    };
  }, [src, shouldLoad]);

  // Handle playback control
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !shouldLoad) return;

    if (autoPlay && isActive) {
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          // Auto-play was prevented
        });
      }
    } else {
      video.pause();
    }
  }, [shouldLoad, autoPlay, isActive, isReady]); // Re-run when ready state changes to retry play if needed

  useEffect(() => {
    if (shouldLoad && videoRef.current) {
      videoRef.current.load();
    }
  }, [src, shouldLoad]);

  const hasPoster = Boolean(poster);
  const isVisible = shouldLoad && (isReady || hasPoster);
  const resolvedPoster = shouldLoad ? poster : undefined;

  return (
    <video
      ref={videoRef}
      className={`transition-opacity duration-500 ease-out ${isVisible ? "opacity-100" : "opacity-0"} ${className}`}
      src={shouldLoad ? src : undefined}
      poster={resolvedPoster}
      loop={loop}
      muted={muted}
      playsInline={playsInline}
      preload={shouldLoad ? "metadata" : "none"}
    />
  );
}
