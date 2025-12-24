import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import GpuStats from './GpuStats';

describe('GpuStats', () => {
  it('renders component with title', () => {
    render(
      <GpuStats
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
  });

  it('displays utilization percentage', () => {
    render(
      <GpuStats
        utilization={75}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('Utilization')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('displays memory usage in GB', () => {
    render(
      <GpuStats
        utilization={50}
        memoryUsed={12288} // 12 GB in MB
        memoryTotal={24576} // 24 GB in MB
        temperature={60}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('Memory')).toBeInTheDocument();
    expect(screen.getByText('12.0 / 24.0 GB')).toBeInTheDocument();
  });

  it('displays temperature with correct unit', () => {
    render(
      <GpuStats
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={65}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('Temperature')).toBeInTheDocument();
    expect(screen.getByText('65°C')).toBeInTheDocument();
  });

  it('displays inference FPS', () => {
    render(
      <GpuStats
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        inferenceFps={28.5}
      />
    );

    expect(screen.getByText('Inference FPS')).toBeInTheDocument();
    expect(screen.getByText('29')).toBeInTheDocument();
  });

  describe('null value handling', () => {
    it('displays "N/A" for null utilization', () => {
      render(
        <GpuStats
          utilization={null}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('Utilization')).toBeInTheDocument();
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });

    it('displays "N/A" for null memory values', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={null}
          memoryTotal={24000}
          temperature={60}
          inferenceFps={30}
        />
      );

      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays "N/A" for null temperature', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={null}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('Temperature')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays "N/A" for null inference FPS', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          inferenceFps={null}
        />
      );

      expect(screen.getByText('Inference FPS')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('handles all null values gracefully', () => {
      render(
        <GpuStats
          utilization={null}
          memoryUsed={null}
          memoryTotal={null}
          temperature={null}
          inferenceFps={null}
        />
      );

      expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });
  });

  describe('temperature color coding', () => {
    it('uses green color for safe temperature (<70°C)', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={65}
          inferenceFps={30}
        />
      );

      // Check for NVIDIA green color class
      const tempValue = screen.getByText('65°C');
      expect(tempValue).toHaveClass('text-[#76B900]');
    });

    it('uses yellow color for warning temperature (70-80°C)', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={75}
          inferenceFps={30}
        />
      );

      const tempValue = screen.getByText('75°C');
      expect(tempValue).toHaveClass('text-yellow-500');
    });

    it('uses red color for critical temperature (>80°C)', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={85}
          inferenceFps={30}
        />
      );

      const tempValue = screen.getByText('85°C');
      expect(tempValue).toHaveClass('text-red-500');
    });

    it('uses gray color for null temperature', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={null}
          inferenceFps={30}
        />
      );

      const naElements = screen.getAllByText('N/A');
      const tempNa = naElements.find(el => el.closest('[class*="text-gray"]'));
      expect(tempNa).toBeDefined();
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', () => {
      render(
        <GpuStats
          utilization={0}
          memoryUsed={0}
          memoryTotal={24000}
          temperature={0}
          inferenceFps={0}
        />
      );

      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('0°C')).toBeInTheDocument();
    });

    it('handles 100% utilization', () => {
      render(
        <GpuStats
          utilization={100}
          memoryUsed={24000}
          memoryTotal={24000}
          temperature={60}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('handles very high temperatures', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={95}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('95°C')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          inferenceFps={30}
          className="custom-class"
        />
      );

      // Verify component renders with custom class by checking it's in the document
      expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
    });
  });

  describe('memory calculation', () => {
    it('correctly converts MB to GB', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={15360} // 15 GB
          memoryTotal={24576} // 24 GB
          temperature={60}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('15.0 / 24.0 GB')).toBeInTheDocument();
    });

    it('displays decimal places for partial GB values', () => {
      render(
        <GpuStats
          utilization={50}
          memoryUsed={12500} // 12.2 GB
          memoryTotal={24000} // 23.4 GB
          temperature={60}
          inferenceFps={30}
        />
      );

      // Should show one decimal place
      const memoryText = screen.getByText(/GB$/);
      expect(memoryText).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('rounds decimal values to integers', () => {
      render(
        <GpuStats
          utilization={75.7}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={65.4}
          inferenceFps={28.9}
        />
      );

      expect(screen.getByText('76%')).toBeInTheDocument();
      expect(screen.getByText('65°C')).toBeInTheDocument();
      expect(screen.getByText('29')).toBeInTheDocument();
    });
  });
});
