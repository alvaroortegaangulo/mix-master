import Image from "next/image";
import { PlayCircleIcon, StarIcon, ExclamationTriangleIcon } from "@heroicons/react/24/solid";
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/routing';

export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  const t = useTranslations('HeroSection');

  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center">

      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-purple-600/10 blur-[120px]" />
      </div>

  
    </section>
  );
}
