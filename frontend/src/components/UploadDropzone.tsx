// frontend/src/components/UploadDropzone.tsx
"use client";

import { useRef, useState } from "react";

type UploadMode = "song" | "stems";

type UploadDropzoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  filesCount?: number;
  uploadMode: UploadMode;
};

export function UploadDropzone({
  onFilesSelected,
  disabled,
  filesCount = 0,
  uploadMode,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const isSongUpload = uploadMode === "song";

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
      f.type.startsWith("audio/"),
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
        "border-slate-700/80 bg-slate-900/40 px-8 py-6 cursor-pointer transition",
        disabled
          ? "opacity-60 cursor-not-allowed"
          : isDragging
          ? "border-teal-400 bg-slate-900/70"
          : "hover:border-teal-400/70 hover:bg-slate-900/70",
      ].join(" ")}
    >
      {/* Cabecera: título dinámico según modo */}
      <div className="mb-4 w-full text-center">
        <p className="text-base font-semibold text-slate-50">
          {isSongUpload ? "Upload Your Song" : "Upload Your Stems"}
        </p>
        <p className="text-xs text-slate-400">
          {isSongUpload
            ? "Master a single stereo bounce."
            : "Upload individual tracks for a full AI mix."}
        </p>
      </div>

      <div className="mt-4 flex justify-center">
        <img
          src="/upload.webp"
          alt="Upload your mix..."
          className="h-18 w-auto rounded-lg"
          width="72"
          height="72"
        />
      </div>

      {/* Texto principal del dropzone, adaptado al modo */}
      <p className="text-sm font-semibold text-slate-50 mb-1 text-center">
        {isSongUpload
          ? "Drag & drop your song here, or click to select a file"
          : "Drag & drop stems here, or click to select files"}
      </p>
      <p className="text-xs text-slate-400 mb-2 text-center">
        Supported formats: WAV
      </p>

      {filesCount > 0 && (
        <p className="mt-1 text-xs text-teal-300">
          {filesCount} audio file{filesCount > 1 ? "s" : ""} selected
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple={uploadMode === "stems"}
        accept={
          uploadMode === "song"
            ? ".wav,audio/wav,audio/x-wav"
            : "audio/*"
        }
        onChange={handleInputChange}
        disabled={disabled}
      />
    </div>
  );
}
