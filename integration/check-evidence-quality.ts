import { Handler } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

// ── Environment ──
const SUPABASE_URL       = process.env.SUPABASE_URL!;
const SUPABASE_KEY       = process.env.SUPABASE_SERVICE_ROLE_KEY!; // service role — server-side only
const CHECKER_URL        = process.env.CHECKER_URL!;               // e.g. "https://checker.polara.app"
const CHECKER_API_KEY    = process.env.CHECKER_API_KEY!;

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

/**
 * Netlify Function: check-evidence-quality
 *
 * Called by the frontend after a user uploads evidence.
 * Orchestrates the round-trip: Supabase Storage → Checker API → Supabase DB.
 *
 * Request body:
 *   { evidence_id: string, control_id: string, storage_path: string }
 *
 * storage_path is the path within the Supabase Storage bucket
 * (e.g. "org_abc/uploads/policy.pdf"). The frontend knows this
 * because it just finished the upload.
 */
export const handler: Handler = async (event) => {
    if (event.httpMethod !== "POST") {
        return { statusCode: 405, body: "Method not allowed" };
    }

    try {
        const { evidence_id, control_id, storage_path } = JSON.parse(event.body || "{}");

        if (!evidence_id || !control_id || !storage_path) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: "Missing evidence_id, control_id, or storage_path" }),
            };
        }

        // ── 1. Fetch the file from Supabase Storage ──
        const { data: fileData, error: downloadError } = await supabase
            .storage
            .from("evidence")                      // bucket name — adjust if different
            .download(storage_path);

        if (downloadError || !fileData) {
            return {
                statusCode: 500,
                body: JSON.stringify({ error: "Failed to download file", detail: downloadError?.message }),
            };
        }

        // ── 2. POST to the checker API ──
        // Build a multipart form with the file blob and control_id.
        const filename = storage_path.split("/").pop() || "evidence.pdf";
        const form = new FormData();
        form.append("file", fileData, filename);
        form.append("control_id", control_id);

        const checkerResponse = await fetch(`${CHECKER_URL}/api/v1/check`, {
            method: "POST",
            headers: { "X-API-Key": CHECKER_API_KEY },
            body: form,
        });

        if (!checkerResponse.ok) {
            const errText = await checkerResponse.text();
            return {
                statusCode: 502,
                body: JSON.stringify({ error: "Checker API error", status: checkerResponse.status, detail: errText }),
            };
        }

        const result = await checkerResponse.json();

        // ── 3. Write the result to Supabase ──
        const { error: insertError } = await supabase
            .from("evidence_quality_scores")
            .insert({
                evidence_id,
                control_id:       result.control_id,
                score:            result.score,
                verdict:          result.verdict,
                explanation:      result.explanation,
                missing_elements: result.missing_elements,
            });

        if (insertError) {
            // Log but don't fail — the checker result is still valid
            console.error("Failed to write score to DB:", insertError.message);
        }

        // ── 4. Return the verdict to the frontend ──
        return {
            statusCode: 200,
            body: JSON.stringify({
                verdict:          result.verdict,
                score:            result.score,
                explanation:      result.explanation,
                missing_elements: result.missing_elements,
            }),
        };

    } catch (err: any) {
        console.error("Unhandled error:", err);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: "Internal error", detail: err.message }),
        };
    }
};