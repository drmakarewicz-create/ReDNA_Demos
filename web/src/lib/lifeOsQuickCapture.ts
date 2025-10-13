import { lifeOs } from './lifeOsClient';

export type QuickCapturePayload = {
  user_id: string;
  text: string;
  when?: string;
  tags?: string[];
  [key: string]: unknown;
};

export async function quickCapture(payload: QuickCapturePayload) {
  const { user_id, ...rest } = payload;
  const path = `/life/${encodeURIComponent(user_id)}/capture`;
  return lifeOs.post(path, rest);
}
