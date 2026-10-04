import { versions } from '../../../../_api.js';

// The versions loaded for queries, newest first.
export const onRequestGet = (context) => versions(context);
