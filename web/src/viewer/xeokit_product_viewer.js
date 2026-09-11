// dev-3 product route: three-cad-viewer is the active interaction shell.
// The XeokitCadViewer alias exists only to keep main_v4 stable on this branch;
// no xeokit package or runtime is used. dev-2 remains the rollback branch.
export {
  ThreeCadProductViewer,
  ThreeCadProductViewer as XeokitCadViewer,
} from './three_cad_product_viewer.js';
