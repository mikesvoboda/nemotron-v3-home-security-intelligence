import { Activity } from 'lucide-react';

export default function Header() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-800 bg-[#1A1A1A] px-6">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-[#76B900]">
            <Activity className="h-5 w-5 text-black" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wide text-white">NVIDIA SECURITY</h1>
            <p className="text-xs font-medium tracking-wider text-[#76B900]">POWERED BY NEMOTRON</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {/* System Status Indicator */}
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
          <span className="text-sm text-gray-400">System Online</span>
        </div>

        {/* GPU Quick Stats Placeholder */}
        <div className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5">
          <div className="text-xs text-gray-400">GPU:</div>
          <div className="text-xs font-semibold text-[#76B900]">--</div>
        </div>
      </div>
    </header>
  );
}
