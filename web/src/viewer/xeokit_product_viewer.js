import { XeokitCadViewer as XeokitBaseViewer } from './xeokit_cad_viewer.js';

/**
 * Product wrapper around the xeokit adapter.
 *
 * main_v4 still contains a few Babylon-era static labels during the migration.
 * Keep those labels truthful without observing the entire workbench DOM. The
 * progress/status updates are frequent during Scania streaming; a subtree
 * MutationObserver here used to turn every update into another render pass.
 * The core adapter remains viewer-agnostic to the surrounding markup.
 */
export class XeokitCadViewer extends XeokitBaseViewer {
  _stampProductUI() {
    if (this._productUIStamped) return;
    const stamp = () => {
      const badge = document.querySelector('#viewer-badge');
      const badgeText = 'XEOKIT · NATIVE OCP · PROXY/DETAIL';
      if (badge && badge.textContent !== badgeText) badge.textContent = badgeText;

      const status = document.querySelector('#status-viewer');
      if (status?.textContent?.includes('Babylon')) {
        status.textContent = status.textContent.replace(/Babylon/gi, 'xeokit');
      }

      const meta = document.querySelector('#viewer-meta');
      if (meta?.textContent?.includes('Babylon')) {
        meta.textContent = meta.textContent.replace(/Babylon/gi, 'xeokit');
      }
    };

    stamp();
    this._productUIStamped = true;
  }
}
