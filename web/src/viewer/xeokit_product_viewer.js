import { ThreeCadProductViewer } from './three_cad_product_viewer.js';

// dev-3 compatibility wrapper: keep main_v4 stable while swapping only the
// Viewer Adapter. The product shell and OCP Runtime stay untouched so this
// branch measures the viewer substrate rather than a UI rewrite.
export class XeokitCadViewer extends ThreeCadProductViewer {
  captureView() {
    // main_v4 persists Evidence synchronously. three-cad's getImage helper is
    // async, so use the rendered canvas directly for the compatibility spike.
    // This keeps the Evidence API contract unchanged while we evaluate the
    // viewer substrate; camera/replay integration can be completed after the
    // dev-3 UX gate passes.
    const canvas = this.host.querySelector('canvas');
    if (!canvas || typeof canvas.toDataURL !== 'function') return null;
    try {
      return canvas.toDataURL('image/png');
    } catch (error) {
      console.warn('three-cad evidence snapshot failed', error);
      return null;
    }
  }
}
