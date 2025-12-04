// frontend/src/components/UploadDropzone.tsx
"use client";

import { useRef, useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

type UploadDropzoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  filesCount?: number;

  /**
   * Modo actual de subida:
   *  - false / undefined => Upload Song
   *  - true              => Upload Stems
   *
   * Si no se pasa, el componente gestiona el estado internamente.
   */
  isStemsMode?: boolean;
  /**
   * Callback opcional para notificar al padre cuando cambia el modo.
   * Se usará para que el backend reciba stems: true/false al lanzar el mix.
   */
  onStemsModeChange?: (isStems: boolean) => void;
};

export function UploadDropzone({
  onFilesSelected,
  disabled,
  filesCount = 0,
  isStemsMode,
  onStemsModeChange,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [internalStems, setInternalStems] = useState(false);

  // Permite modo controlado o no controlado
  const isStems = isStemsMode ?? internalStems;

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

  const handleToggleChange = (checked: boolean) => {
    // notificar al padre si lo desea
    onStemsModeChange?.(checked);

    // si el padre no controla el valor, lo guardamos localmente
    if (isStemsMode === undefined) {
      setInternalStems(checked);
    }
  };

  const panelTitle = isStems ? "Upload Your Stems" : "Upload Your Song";

  return (
    <div className="w-full space-y-4">
      {/* Cabecera con título y toggle arriba a la derecha */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-50">
          {panelTitle}
        </h2>

        <div className="flex items-center space-x-2">
          <Label
            htmlFor="stems-mode-toggle"
            className="text-sm text-slate-300"
          >
            Upload Stems
          </Label>
          <Switch
            id="stems-mode-toggle"
            checked={isStems}
            onCheckedChange={handleToggleChange}
            disabled={disabled}
          />
        </div>
      </div>

      {/* Área de drop */}
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

        <p className="text-lg font-semibold text-slate-50 mb-1 text-center">
          Drag & drop audio {isStems ? "stems" : "file"} here, or click to
          select {isStems ? "stems" : "a file"}
        </p>
        <p className="text-sm text-slate-400 mb-2 text-center">
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
    </div>
  );
}
