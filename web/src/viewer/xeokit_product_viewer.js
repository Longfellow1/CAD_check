// dev-3 compatibility export: keep main_v4 stable while swapping only the
// Viewer Adapter. The product shell and OCP Runtime stay untouched so this
// branch measures the viewer substrate rather than a UI rewrite.
export { ThreeCadProductViewer as XeokitCadViewer } from './three_cad_product_viewer.js';
