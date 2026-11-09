import { json } from '@sveltejs/kit';

// Solo expone la clave publicable de Clerk; la clave secreta nunca llega al navegador.
export function GET() {
  return json({ publishableKey: String(process.env.PUBLIC_CLERK_PUBLISHABLE_KEY ?? '') });
}
