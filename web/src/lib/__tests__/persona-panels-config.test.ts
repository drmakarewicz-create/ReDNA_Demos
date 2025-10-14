/**
 * Unit tests for persona-panels-config
 */

import {
  getPersonaPanelConfig,
  shouldShowLifeOS,
  getLifeOSVariant,
  getPersonaPanels,
  type LifeOSVariant,
  type PersonaPanelConfig,
} from '../persona-panels-config';

describe('persona-panels-config', () => {
  describe('getPersonaPanelConfig', () => {
    it('returns head_coach config for head_coach', () => {
      const config = getPersonaPanelConfig('head_coach');
      expect(config.lifeOS).toBe('full');
      expect(config.panels).toEqual([]);
    });

    it('returns relationship_coach config for relationship_coach', () => {
      const config = getPersonaPanelConfig('relationship_coach');
      expect(config.lifeOS).toBe('relationship');
      expect(config.panels).toEqual([]);
    });

    it('returns photo config for photo_coach', () => {
      const config = getPersonaPanelConfig('photo_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(1);
      expect(config.panels[0].id).toBe('photo');
    });

    it('returns photo config for photo (without _coach suffix)', () => {
      const config = getPersonaPanelConfig('photo');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(1);
      expect(config.panels[0].id).toBe('photo');
    });

    it('returns padna config for padna_coach', () => {
      const config = getPersonaPanelConfig('padna_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(1);
      expect(config.panels[0].id).toBe('padna');
    });

    it('returns padna config for padna (without _coach suffix)', () => {
      const config = getPersonaPanelConfig('padna');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(1);
      expect(config.panels[0].id).toBe('padna');
    });

    it('returns rendering config for rendering', () => {
      const config = getPersonaPanelConfig('rendering');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(2);
      expect(config.panels[0].id).toBe('avatar');
      expect(config.panels[1].id).toBe('portrait');
    });

    it('returns career_coach config for career_coach', () => {
      const config = getPersonaPanelConfig('career_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(2);
      expect(config.panels[0].id).toBe('career_snapshot');
      expect(config.panels[1].id).toBe('skill_map');
    });

    it('returns personality_test_coach config for personality_test_coach', () => {
      const config = getPersonaPanelConfig('personality_test_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(2);
      expect(config.panels[0].id).toBe('personality_snapshot');
      expect(config.panels[1].id).toBe('personality_map');
    });

    it('returns chatdna_coach config for chatdna_coach', () => {
      const config = getPersonaPanelConfig('chatdna_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels.length).toBe(2);
      expect(config.panels[0].id).toBe('chatdna_snapshot');
      expect(config.panels[1].id).toBe('language_style');
    });

    it('returns beliefdna_coach config for beliefdna_coach', () => {
      const config = getPersonaPanelConfig('beliefdna_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels).toEqual([]);
    });

    it('returns permission_coach config for permission_coach', () => {
      const config = getPersonaPanelConfig('permission_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels).toEqual([]);
    });

    it('returns default config for unknown persona', () => {
      const config = getPersonaPanelConfig('unknown_coach');
      expect(config.lifeOS).toBe('hidden');
      expect(config.panels).toEqual([]);
    });

    it('normalizes persona key (case insensitive)', () => {
      const config1 = getPersonaPanelConfig('HEAD_COACH');
      const config2 = getPersonaPanelConfig('head_coach');
      expect(config1).toEqual(config2);
    });

    it('normalizes persona key (trims whitespace)', () => {
      const config1 = getPersonaPanelConfig('  photo_coach  ');
      const config2 = getPersonaPanelConfig('photo_coach');
      expect(config1).toEqual(config2);
    });
  });

  describe('shouldShowLifeOS', () => {
    it('returns true for head_coach', () => {
      expect(shouldShowLifeOS('head_coach')).toBe(true);
    });

    it('returns true for relationship_coach', () => {
      expect(shouldShowLifeOS('relationship_coach')).toBe(true);
    });

    it('returns false for photo_coach', () => {
      expect(shouldShowLifeOS('photo_coach')).toBe(false);
    });

    it('returns false for padna_coach', () => {
      expect(shouldShowLifeOS('padna_coach')).toBe(false);
    });

    it('returns false for career_coach', () => {
      expect(shouldShowLifeOS('career_coach')).toBe(false);
    });

    it('returns false for unknown persona', () => {
      expect(shouldShowLifeOS('unknown_coach')).toBe(false);
    });
  });

  describe('getLifeOSVariant', () => {
    it('returns full for head_coach', () => {
      expect(getLifeOSVariant('head_coach')).toBe('full');
    });

    it('returns relationship for relationship_coach', () => {
      expect(getLifeOSVariant('relationship_coach')).toBe('relationship');
    });

    it('returns hidden for photo_coach', () => {
      expect(getLifeOSVariant('photo_coach')).toBe('hidden');
    });

    it('returns hidden for unknown persona', () => {
      expect(getLifeOSVariant('unknown_coach')).toBe('hidden');
    });
  });

  describe('getPersonaPanels', () => {
    it('returns empty array for head_coach', () => {
      const panels = getPersonaPanels('head_coach');
      expect(panels).toEqual([]);
    });

    it('returns sorted panels for photo_coach', () => {
      const panels = getPersonaPanels('photo_coach');
      expect(panels.length).toBe(1);
      expect(panels[0].id).toBe('photo');
      expect(panels[0].order).toBe(10);
    });

    it('returns sorted panels for rendering', () => {
      const panels = getPersonaPanels('rendering');
      expect(panels.length).toBe(2);
      // Should be sorted by order (ascending)
      expect(panels[0].id).toBe('avatar');
      expect(panels[0].order).toBe(10);
      expect(panels[1].id).toBe('portrait');
      expect(panels[1].order).toBe(20);
    });

    it('returns sorted panels for career_coach', () => {
      const panels = getPersonaPanels('career_coach');
      expect(panels.length).toBe(2);
      expect(panels[0].id).toBe('career_snapshot');
      expect(panels[0].order).toBe(10);
      expect(panels[1].id).toBe('skill_map');
      expect(panels[1].order).toBe(20);
    });

    it('passes props to panels', () => {
      const panels = getPersonaPanels('career_coach');
      expect(panels[1].props).toEqual({ minCuriosity: 50 });
    });

    it('filters panels by feature flags when provided', () => {
      // Assuming we add a panel with a featureFlag later
      const panels = getPersonaPanels('career_coach', {
        someFeature: false,
      });
      // All current panels have no featureFlag, so all should be returned
      expect(panels.length).toBe(2);
    });

    it('sorts panels by order ascending', () => {
      // Test with a persona that has multiple panels
      const panels = getPersonaPanels('career_coach');
      for (let i = 1; i < panels.length; i++) {
        expect(panels[i].order).toBeGreaterThanOrEqual(panels[i - 1].order);
      }
    });
  });

  describe('panel order consistency', () => {
    it('ensures all panels have valid order values', () => {
      const allPersonas = [
        'head_coach',
        'relationship_coach',
        'photo_coach',
        'photo',
        'padna_coach',
        'padna',
        'rendering',
        'career_coach',
        'personality_test_coach',
        'chatdna_coach',
        'beliefdna_coach',
        'permission_coach',
      ];

      allPersonas.forEach((persona) => {
        const config = getPersonaPanelConfig(persona);
        config.panels.forEach((panel) => {
          expect(typeof panel.order).toBe('number');
          expect(panel.order).toBeGreaterThan(0);
          expect(panel.id).toBeTruthy();
          expect(panel.component).toBeTruthy();
        });
      });
    });
  });

  describe('config shape validation', () => {
    it('ensures all configs have required fields', () => {
      const allPersonas = [
        'head_coach',
        'relationship_coach',
        'photo_coach',
        'padna_coach',
        'rendering',
        'career_coach',
        'personality_test_coach',
        'chatdna_coach',
        'beliefdna_coach',
        'permission_coach',
      ];

      allPersonas.forEach((persona) => {
        const config = getPersonaPanelConfig(persona);
        expect(config).toHaveProperty('lifeOS');
        expect(config).toHaveProperty('panels');
        expect(Array.isArray(config.panels)).toBe(true);
        expect(['full', 'relationship', 'hidden']).toContain(config.lifeOS);
      });
    });
  });
});
