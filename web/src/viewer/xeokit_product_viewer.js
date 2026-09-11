import { XeokitCadViewer as XeokitBaseViewer } from './xeokit_cad_viewer.js';

/**
 * Product wrapper around the xeokit adapter.
 *
 * main_v4 still contains a few Babylon-era static labels during the migration.
 * Keep those labels truthful without allowing DOM MutationObserver feedback to
 * starve the Renderer event loop. The core adapter remains viewer-agnostic to
 * the surrounding workbench markup.
 */
export class XeokitCadViewer extends XeokitBaseViewer {
  _stampProductUI() {
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
    if (this._labelObserver) return;
    this._labelObserver = new MutationObserver(stamp);
    const root = document.querySelector('.shell') || document.body;
    this._labelObserver.observe(root, {subtree:true, childList:true, characterData:true});
  }
}
