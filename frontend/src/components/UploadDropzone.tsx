// frontend/src/components/UploadDropzone.tsx
"use client";

import { useRef, useState } from "react";

type UploadMode = "song" | "stems";

type UploadDropzoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  filesCount?: number;
  /**
   * Modo de subida controlado desde el padre (opcional).
   * Si no se pasa, el componente gestionará el modo internamente.
   */
  uploadMode?: UploadMode;
  /**
   * Callback opcional para notificar al padre cambios de modo.
   */
  onUploadModeChange?: (mode: UploadMode) => void;
};

export function UploadDropzone({
  onFilesSelected,
  disabled,
  filesCount = 0,
  uploadMode,
  onUploadModeChange,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [localMode, setLocalMode] = useState<UploadMode>("song");
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Si el padre no controla el modo, usamos el interno
  const effectiveMode: UploadMode = uploadMode ?? localMode;
  const isSongUpload = effectiveMode === "song";

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

  const handleModeChange = (mode: UploadMode) => {
    if (disabled) return;

    // Si el modo no está controlado desde fuera, actualizamos el local
    if (!uploadMode) {
      setLocalMode(mode);
    }

    // Notificamos al padre si quiere reaccionar (para mandar stems=true/false al backend)
    if (onUploadModeChange) {
      onUploadModeChange(mode);
    }
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
      {/* Cabecera: título + toggle simple */}
      <div className="mb-4 flex w-full items-center justify-between gap-3">
        <div className="flex flex-col">
          <p className="text-base font-semibold text-slate-50">
            {isSongUpload ? "Upload Your Song" : "Upload Your Stems"}
          </p>
        </div>

        {/* Toggle Song / Stems */}
        <div
          className="inline-flex items-center gap-1 rounded-full bg-slate-800/80 p-1 text-xs"
          onClick={(e) => {
            // Evitamos que el click abra el diálogo de archivos
            e.stopPropagation();
          }}
        >
          <button
            type="button"
            className={[
              "px-2 py-1 rounded-full font-medium transition",
              !isSongUpload
                ? "text-slate-300"
                : "bg-teal-500 text-slate-900 shadow",
            ].join(" ")}
            disabled={disabled}
            onClick={() => handleModeChange("song")}
          >
            Song
          </button>
          <button
            type="button"
            className={[
              "px-2 py-1 rounded-full font-medium transition",
              isSongUpload
                ? "text-slate-300"
                : "bg-teal-500 text-slate-900 shadow",
            ].join(" ")}
            disabled={disabled}
            onClick={() => handleModeChange("stems")}
          >
            Stems
          </button>
        </div>
      </div>

      <div className="mt-4 flex justify-center">
        <img
          src="/upload.gif"
          alt="Upload your mix..."
          className="h-24 w-auto rounded-lg"
        />
      </div>

      {/* Texto principal del dropzone, adaptado al modo */}
      <p className="text-sm font-semibold text-slate-50 mb-1 text-center">
        {isSongUpload
          ? "Drag & drop your song here, or click to select a file"
          : "Drag & drop stems here, or click to select files"}
      </p>
      <p className="text-xs text-slate-400 mb-2 text-center">
        Supported formats: WAV, MP3, AIFF, FLAC
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
        multiple
        accept="audio/*"
        onChange={handleInputChange}
        disabled={disabled}
      />
    </div>
  );
}
