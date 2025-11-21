// frontend/src/components/UploadDropzone.tsx
"use client";

import { useRef, useState } from "react";

type UploadDropzoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  filesCount?: number;
};

export function UploadDropzone({
  onFilesSelected,
  disabled,
  filesCount = 0,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleClick = () => {
    if (disabled) return;
    inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    onFilesSelected(selected);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled) return;
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith("audio/")
    );

    if (droppedFiles.length > 0) {
      onFilesSelected(droppedFiles);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled) return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={[
        "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed",
        "border-slate-700/80 bg-slate-900/40 px-8 py-16 cursor-pointer transition",
        disabled
          ? "opacity-60 cursor-not-allowed"
          : isDragging
          ? "border-teal-400 bg-slate-900/70"
          : "hover:border-teal-400/70 hover:bg-slate-900/70",
      ].join(" ")}
    >
      {/* Icono simplito */}
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-slate-600 bg-slate-900">
        <span className="text-3xl leading-none">⬆️</span>
      </div>

      <p className="text-lg font-semibold text-slate-50 mb-1">
        Drag & drop stems here, or click to select files
      </p>
      <p className="text-sm text-slate-400 mb-2">
        Supported formats: WAV, MP3, AIFF, FLAC
      </p>

      {filesCount > 0 && (
        <p className="mt-2 text-sm text-teal-300">
          {filesCount} audio file{filesCount > 1 ? "s" : ""} selected
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple
        accept="audio/*"
        onChange={handleInputChange}
        disabled={disabled}
      />
    </div>
  );
}
