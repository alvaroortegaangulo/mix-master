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
};

export function LazyVideo({
  src,
  className = "",
  poster,
  autoPlay = true,
  loop = true,
  muted = true,
  playsInline = true,
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
      { threshold: 0.25 }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setIsReady(false);
    if (!shouldLoad || !videoRef.current) return;

    const video = videoRef.current;
    const handleReady = () => setIsReady(true);
    video.addEventListener("loadeddata", handleReady);

    if (autoPlay) {
      const play = () => {
        void video.play().catch(() => {});
      };
      const id = requestAnimationFrame(play);
      return () => {
        cancelAnimationFrame(id);
        video.removeEventListener("loadeddata", handleReady);
      };
    }

    return () => {
      video.removeEventListener("loadeddata", handleReady);
    };
  }, [shouldLoad, autoPlay, src]);

  useEffect(() => {
    if (shouldLoad && videoRef.current) {
      videoRef.current.load();
    }
  }, [src, shouldLoad]);

  return (
    <video
      ref={videoRef}
      className={`transition-opacity duration-500 ease-out ${isReady ? "opacity-100" : "opacity-0"} ${className}`}
      src={shouldLoad ? src : undefined}
      poster={poster}
      loop={loop}
      muted={muted}
      playsInline={playsInline}
      autoPlay={shouldLoad && autoPlay}
      preload={shouldLoad ? "metadata" : "none"}
    />
  );
}
