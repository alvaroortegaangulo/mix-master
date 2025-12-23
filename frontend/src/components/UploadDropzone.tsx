"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CloudArrowUpIcon } from "@heroicons/react/24/solid";
import { ProcessingVisualizer } from "./ProcessingVisualizer";

type UploadMode = "song" | "stems";

type UploadDropzoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  filesCount?: number;
  uploadMode: UploadMode;
  isProcessing?: boolean;
  processingState?: {
    stageKey: string;
    progress: number;
    description: string;
  };
};

export function UploadDropzone({
  onFilesSelected,
  disabled,
  filesCount = 0,
  uploadMode,
  isProcessing,
  processingState,
}: UploadDropzoneProps) {
  const t = useTranslations("UploadDropzone");
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const isSongUpload = uploadMode === "song";

  const handleClick = () => {
    if (disabled || isProcessing) return;
    inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    onFilesSelected(selected);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled || isProcessing) return;
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith("audio/"),
    );

    if (droppedFiles.length > 0) {
      onFilesSelected(droppedFiles);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled || isProcessing) return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  if (isProcessing && processingState) {
    return (
        <div className="w-full h-full min-h-[400px] flex items-stretch justify-stretch">
            <ProcessingVisualizer
                stageKey={processingState.stageKey}
                progress={processingState.progress}
                description={processingState.description}
            />
        </div>
    );
  }

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={[
        "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed w-full",
        "border-slate-800 bg-slate-950/20 px-8 py-12 cursor-pointer transition min-h-[400px]",
        disabled
          ? "opacity-60 cursor-not-allowed"
          : isDragging
          ? "border-teal-400 bg-slate-900/70"
          : "hover:border-teal-500/50 hover:bg-slate-900/40",
      ].join(" ")}
    >
      <div className="relative flex items-center justify-center w-24 h-24 mb-8 rounded-full bg-slate-900 shadow-2xl ring-1 ring-slate-800">
        <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/20 to-blue-500/10 rounded-full blur-xl" />
        <CloudArrowUpIcon className="w-10 h-10 text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]" />
      </div>

      {/* Texto principal del dropzone, adaptado al modo */}
      <p className="text-lg font-medium text-white mb-3 text-center tracking-wide">
        {isSongUpload ? t("dragDropSong") : t("dragDropStems")}
      </p>
      <p className="text-xs font-medium text-slate-500 mb-8 text-center uppercase tracking-wider">
        {t("supportedFormats")}
      </p>

      <button
        type="button"
        className="px-6 py-2.5 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 text-sm font-bold transition-colors shadow-[0_0_15px_rgba(20,184,166,0.3)]"
      >
        {t("orSelectFiles")}
      </button>

      {filesCount > 0 && (
        <p className="mt-6 text-sm font-medium text-teal-400 animate-in fade-in slide-in-from-bottom-2">
          {t("filesSelected", { count: filesCount })}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple={uploadMode === "stems"}
        accept={
          uploadMode === "song"
            ? ".wav,.aif,.aiff,.mp3,audio/wav,audio/x-wav,audio/aiff,audio/x-aiff,audio/mpeg,audio/mp3"
            : "audio/*"
        }
        onChange={handleInputChange}
        disabled={disabled}
      />
    </div>
  );
}
