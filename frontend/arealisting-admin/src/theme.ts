import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

// Aura components share the same yellow actions and graphite text as the workspace.
export const undersunPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#fffaf0',
      100: '#fff2c6',
      200: '#ffe69a',
      300: '#ffda63',
      400: '#ffca2b',
      500: '#f8bd00',
      600: '#d9a400',
      700: '#ad8200',
      800: '#806100',
      900: '#5d4600',
      950: '#3d2e00',
    },
    colorScheme: {
      light: {
        primary: {
          color: '#f8bd00',
          inverseColor: '#182239',
          hoverColor: '#e5ad00',
          activeColor: '#d9a400',
        },
        highlight: {
          background: '#fff8df',
          focusBackground: '#fff0bd',
          color: '#705300',
          focusColor: '#4d3900',
        },
      },
    },
  },
});
