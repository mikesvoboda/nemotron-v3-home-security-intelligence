import { Activity } from 'lucide-react';

export default function Header() {
  return (
    <header className="h-16 bg-[#1A1A1A] border-b border-gray-800 px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-[#76B900] rounded flex items-center justify-center">
            <Activity className="w-5 h-5 text-black" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide">
              NVIDIA SECURITY
            </h1>
            <p className="text-xs text-[#76B900] font-medium tracking-wider">
              POWERED BY NEMOTRON
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {/* System Status Indicator */}
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-sm text-gray-400">System Online</span>
        </div>

        {/* GPU Quick Stats Placeholder */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg">
          <div className="text-xs text-gray-400">GPU:</div>
          <div className="text-xs font-semibold text-[#76B900]">--</div>
        </div>
      </div>
    </header>
  );
}
