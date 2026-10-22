/**
 * Model-specific configuration forms for Prompt Management
 *
 * @see NEM-2697 - Build Prompt Management page
 *
 * B3.3 box 4 (R2a row 27): the Florence-2, YOLO-World, X-CLIP and Fashion-CLIP forms
 * retired with the models themselves (the R8 S2/S3 serving sweep); nemotron is the
 * only model a deployment boots, so it is the only editor here.
 */

export { default as NemotronConfigForm } from './NemotronConfigForm';
export type { NemotronConfigFormProps } from './NemotronConfigForm';
