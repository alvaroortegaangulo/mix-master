import React from "react";
import { UserCircleIcon } from "@heroicons/react/24/solid";

export default function BlogAuthor() {
  return (
    <div className="mt-16 flex flex-col items-center gap-6 rounded-2xl border border-slate-800 bg-slate-900/50 p-8 text-center sm:flex-row sm:text-left">
      <div className="relative shrink-0">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-slate-800 text-slate-600 ring-4 ring-slate-900 ring-offset-2 ring-offset-slate-800">
           <UserCircleIcon className="h-12 w-12" />
        </div>
      </div>
      <div>
        <h3 className="text-xl font-bold text-white">Piroola Team</h3>
        <p className="text-sm font-medium text-teal-400">Audio Engineering & AI</p>
        <p className="mt-3 text-slate-400 text-sm leading-relaxed">
          Somos un equipo de ingenieros de mezcla y desarrolladores apasionados por democratizar el sonido profesional.
          Nuestro objetivo es ayudarte a conseguir mezclas listas para streaming sin complicaciones técnicas.
        </p>
      </div>
    </div>
  );
}
