import Link from "next/link";
import Image from "next/image";

export function Footer() {
  return (
    <footer className="bg-slate-950 border-t border-slate-800 py-12 px-4 z-10 relative">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8 text-slate-400 text-sm">
        <div className="flex items-center gap-2">
           <Image src="/logo.webp" alt="Piroola Logo" width={24} height={24} className="h-6 w-6" />
           <span className="font-semibold text-slate-200">Piroola</span>
        </div>
        <div className="flex gap-6">
          <Link href="/terms-of-service" className="hover:text-white transition">Terms</Link>
          <Link href="/privacy-policy" className="hover:text-white transition">Privacy</Link>
          <Link href="/cookie-policy" className="hover:text-white transition">Cookies</Link>
          <Link href="/support" className="hover:text-white transition">Contact</Link>
        </div>
        <div>
            © 2025 Piroola.
        </div>
      </div>
    </footer>
  );
}
