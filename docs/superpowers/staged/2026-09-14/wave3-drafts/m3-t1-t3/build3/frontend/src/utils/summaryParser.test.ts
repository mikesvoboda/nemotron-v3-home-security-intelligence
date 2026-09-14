/**
 * Tests for Summary Parser Utility
 *
 * @see NEM-2923
 */

import { describe, expect, it } from 'vitest';

import {
  extractBulletPoints,
  extractCameraNames,
  extractPatterns,
  extractTimeRange,
  extractWeatherConditions,
} from './summaryParser';

describe('summaryParser', () => {
  describe('extractBulletPoints', () => {
    describe('time extraction', () => {
      it('extracts 12-hour time format', () => {
        const content = 'Activity detected at 2:15 PM';
        const bullets = extractBulletPoints(content);
        const timeBullet = bullets.find((b) => b.icon === 'time');
        expect(timeBullet).toBeDefined();
        expect(timeBullet?.text).toContain('2:15 PM');
      });

      it('extracts time ranges', () => {
        const content = 'Activity from 2:15 PM to 3:00 PM';
        const bullets = extractBulletPoints(content);
        const timeBullet = bullets.find((b) => b.icon === 'time');
        expect(timeBullet).toBeDefined();
        expect(timeBullet?.text).toMatch(/2:15 PM.*3:00 PM/);
      });

      it('extracts 24-hour time format', () => {
        const content = 'Event occurred at 14:30';
        const bullets = extractBulletPoints(content);
        const timeBullet = bullets.find((b) => b.icon === 'time');
        expect(timeBullet).toBeDefined();
        expect(timeBullet?.text).toContain('14:30');
      });
    });

    describe('location extraction', () => {
      it('extracts front door location', () => {
        const content = 'Person detected at the front door';
        const bullets = extractBulletPoints(content);
        const locationBullet = bullets.find((b) => b.icon === 'location');
        expect(locationBullet).toBeDefined();
        expect(locationBullet?.text.toLowerCase()).toContain('front door');
      });

      it('extracts garage location', () => {
        const content = 'Activity in the garage area';
        const bullets = extractBulletPoints(content);
        const locationBullet = bullets.find((b) => b.icon === 'location');
        expect(locationBullet).toBeDefined();
        expect(locationBullet?.text.toLowerCase()).toContain('garage');
      });

      it('extracts driveway location', () => {
        const content = 'Vehicle seen in driveway camera';
        const bullets = extractBulletPoints(content);
        const locationBullet = bullets.find((b) => b.icon === 'location');
        expect(locationBullet).toBeDefined();
        expect(locationBullet?.text.toLowerCase()).toContain('driveway');
      });

      it('limits locations to 2', () => {
        const content = 'Activity at front door, garage, backyard, and porch';
        const bullets = extractBulletPoints(content);
        const locationBullets = bullets.filter((b) => b.icon === 'location');
        expect(locationBullets.length).toBeLessThanOrEqual(2);
      });
    });

    describe('activity/pattern extraction', () => {
      it('extracts person detection', () => {
        const content = 'A person was detected at the entrance';
        const bullets = extractBulletPoints(content);
        const activityBullet = bullets.find((b) => b.icon === 'pattern' || b.icon === 'alert');
        expect(activityBullet).toBeDefined();
        expect(activityBullet?.text.toLowerCase()).toContain('person');
      });

      it('extracts vehicle detection', () => {
        const content = 'Vehicle detected in the driveway';
        const bullets = extractBulletPoints(content);
        const activityBullet = bullets.find((b) => b.icon === 'pattern' || b.icon === 'alert');
        expect(activityBullet).toBeDefined();
        expect(activityBullet?.text.toLowerCase()).toContain('vehicle');
      });

      it('extracts multiple activities', () => {
        const content = 'Person and vehicle detected near the gate';
        const bullets = extractBulletPoints(content);
        const activityBullet = bullets.find((b) => b.icon === 'pattern' || b.icon === 'alert');
        expect(activityBullet).toBeDefined();
        expect(activityBullet?.text.toLowerCase()).toMatch(/person.*vehicle|vehicle.*person/);
      });

      it('extracts delivery detection', () => {
        const content = 'Package delivery completed at front door';
        const bullets = extractBulletPoints(content);
        const activityBullet = bullets.find((b) => b.icon === 'pattern' || b.icon === 'alert');
        expect(activityBullet).toBeDefined();
        // Should contain either package or delivery
        expect(activityBullet?.text.toLowerCase()).toMatch(/package|delivery/);
      });
    });

    describe('weather extraction', () => {
      it('extracts sunny weather', () => {
        const content = 'Activity detected on a sunny afternoon';
        const bullets = extractBulletPoints(content);
        const weatherBullet = bullets.find((b) => b.icon === 'weather');
        expect(weatherBullet).toBeDefined();
        expect(weatherBullet?.text.toLowerCase()).toContain('sunny');
      });

      it('extracts rainy weather', () => {
        const content = 'Detection during rainy conditions';
        const bullets = extractBulletPoints(content);
        const weatherBullet = bullets.find((b) => b.icon === 'weather');
        expect(weatherBullet).toBeDefined();
        expect(weatherBullet?.text.toLowerCase()).toContain('rainy');
      });

      it('extracts cloudy weather', () => {
        const content = 'Activity under cloudy skies';
        const bullets = extractBulletPoints(content);
        const weatherBullet = bullets.find((b) => b.icon === 'weather');
        expect(weatherBullet).toBeDefined();
        expect(weatherBullet?.text.toLowerCase()).toContain('cloudy');
      });
    });

    describe('severity detection', () => {
      it('assigns critical severity for critical keywords', () => {
        // Content needs an activity pattern (person, vehicle, etc.) to create a bullet with severity
        const content = 'Critical intruder person detected at front door';
        const bullets = extractBulletPoints(content);
        const severityBullet = bullets.find((b) => b.severity !== undefined);
        expect(severityBullet).toBeDefined();
        expect(severityBullet?.severity).toBe(90);
      });

      it('assigns high severity for suspicious keywords', () => {
        const content = 'Suspicious person loitering near entrance';
        const bullets = extractBulletPoints(content);
        const severityBullet = bullets.find((b) => b.severity !== undefined);
        expect(severityBullet).toBeDefined();
        expect(severityBullet?.severity).toBe(70);
      });

      it('assigns medium severity for unusual keywords', () => {
        const content = 'Unusual activity detected at the gate';
        const bullets = extractBulletPoints(content);
        const severityBullet = bullets.find((b) => b.severity !== undefined);
        expect(severityBullet).toBeDefined();
        expect(severityBullet?.severity).toBe(50);
      });

      it('assigns low severity for routine keywords', () => {
        const content = 'Routine delivery person at door';
        const bullets = extractBulletPoints(content);
        const severityBullet = bullets.find((b) => b.severity !== undefined);
        expect(severityBullet).toBeDefined();
        expect(severityBullet?.severity).toBe(20);
      });

      it('uses alert icon for high severity patterns', () => {
        const content = 'Suspicious person detected at front door';
        const bullets = extractBulletPoints(content);
        const activityBullet = bullets.find((b) => b.severity && b.severity >= 50);
        expect(activityBullet?.icon).toBe('alert');
      });
    });

    describe('edge cases', () => {
      it('returns empty array for empty content', () => {
        const bullets = extractBulletPoints('');
        expect(bullets).toEqual([]);
      });

      it('returns empty array for null content', () => {
        const bullets = extractBulletPoints(null as unknown as string);
        expect(bullets).toEqual([]);
      });

      it('returns empty array for undefined content', () => {
        const bullets = extractBulletPoints(undefined as unknown as string);
        expect(bullets).toEqual([]);
      });

      it('creates fallback bullet for unstructured content', () => {
        const content = 'Some activity was recorded but no specific details available.';
        const bullets = extractBulletPoints(content);
        expect(bullets.length).toBeGreaterThan(0);
      });

      it('truncates very long fallback content', () => {
        const content = 'A'.repeat(100);
        const bullets = extractBulletPoints(content);
        const fallbackBullet = bullets.find((b) => b.text.endsWith('...'));
        expect(fallbackBullet).toBeDefined();
        expect(fallbackBullet?.text.length).toBeLessThanOrEqual(80);
      });
    });

    describe('complex scenarios', () => {
      it('extracts all components from a complete summary', () => {
        const content =
          'At 2:15 PM, a suspicious person was detected at the front door camera during cloudy weather.';
        const bullets = extractBulletPoints(content);

        const timeBullet = bullets.find((b) => b.icon === 'time');
        const locationBullet = bullets.find((b) => b.icon === 'location');
        const activityBullet = bullets.find((b) => b.icon === 'alert' || b.icon === 'pattern');
        const weatherBullet = bullets.find((b) => b.icon === 'weather');

        expect(timeBullet).toBeDefined();
        expect(locationBullet).toBeDefined();
        expect(activityBullet).toBeDefined();
        expect(weatherBullet).toBeDefined();
      });
    });
  });

  describe('extractTimeRange', () => {
    it('extracts single time', () => {
      const result = extractTimeRange('Event at 2:15 PM');
      expect(result).toContain('2:15 PM');
    });

    it('extracts time range from multiple times', () => {
      const result = extractTimeRange('Activity between 2:15 PM and 3:00 PM');
      expect(result).toContain('2:15 PM');
      expect(result).toContain('3:00 PM');
    });

    it('returns undefined for content without times', () => {
      const result = extractTimeRange('Some activity occurred');
      expect(result).toBeUndefined();
    });

    it('returns undefined for empty content', () => {
      const result = extractTimeRange('');
      expect(result).toBeUndefined();
    });
  });

  describe('extractCameraNames', () => {
    it('extracts front door camera', () => {
      const result = extractCameraNames('Activity at the front door camera');
      expect(result.some((name) => name.toLowerCase().includes('front door'))).toBe(true);
    });

    it('extracts multiple cameras', () => {
      const result = extractCameraNames('Activity at front door and garage');
      expect(result.length).toBeGreaterThan(0);
    });

    it('returns empty array for no cameras', () => {
      const result = extractCameraNames('Some generic activity');
      expect(result).toEqual([]);
    });

    it('capitalizes camera names', () => {
      const result = extractCameraNames('Activity at the front door');
      const frontDoorEntry = result.find((name) => name.toLowerCase().includes('front'));
      expect(frontDoorEntry?.[0]).toMatch(/[A-Z]/); // First letter should be capitalized
    });
  });

  describe('extractPatterns', () => {
    it('extracts person pattern', () => {
      const result = extractPatterns('A person was detected');
      expect(result.some((p) => p.toLowerCase().includes('person'))).toBe(true);
    });

    it('extracts vehicle pattern', () => {
      const result = extractPatterns('Vehicle detected in driveway');
      expect(result.some((p) => p.toLowerCase().includes('vehicle'))).toBe(true);
    });

    it('extracts multiple patterns', () => {
      const result = extractPatterns('Person and vehicle detected');
      expect(result.length).toBeGreaterThanOrEqual(2);
    });

    it('removes duplicate patterns', () => {
      const result = extractPatterns('Person detected, another person seen');
      const personCount = result.filter((p) => p.toLowerCase() === 'person').length;
      expect(personCount).toBe(1);
    });

    it('returns empty array for no patterns', () => {
      // Use content without any ACTIVITY_PATTERNS keywords (person, vehicle, animal, package, motion, activity)
      const result = extractPatterns('Something happened here');
      expect(result).toEqual([]);
    });
  });

  describe('extractWeatherConditions', () => {
    it('extracts sunny weather', () => {
      const result = extractWeatherConditions('Sunny day observation');
      expect(result?.toLowerCase()).toContain('sunny');
    });

    it('extracts cloudy weather', () => {
      const result = extractWeatherConditions('Cloudy conditions');
      expect(result?.toLowerCase()).toContain('cloudy');
    });

    it('extracts rainy weather', () => {
      const result = extractWeatherConditions('Rain detected');
      expect(result?.toLowerCase()).toMatch(/rain/);
    });

    it('returns undefined for no weather', () => {
      const result = extractWeatherConditions('Some activity detected');
      expect(result).toBeUndefined();
    });

    it('returns first weather condition when multiple exist', () => {
      const result = extractWeatherConditions('Sunny then cloudy');
      expect(result).toBeDefined();
      expect(result?.toLowerCase()).toMatch(/sunny|cloudy/);
    });
  });
});
