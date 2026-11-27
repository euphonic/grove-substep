import { describe, expect, it } from 'vitest';
import { parseSSE, type SSEEvent } from './sse';

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
	const enc = new TextEncoder();
	return new ReadableStream({
		start(controller) {
			for (const c of chunks) controller.enqueue(enc.encode(c));
			controller.close();
		}
	});
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SSEEvent[]> {
	const out: SSEEvent[] = [];
	for await (const e of parseSSE(stream)) out.push(e);
	return out;
}

describe('parseSSE', () => {
	it('parses complete events', async () => {
		const events = await collect(
			streamOf('event: token\ndata: {"text":"Hi"}\n\nevent: end\ndata: {"crisis":false}\n\n')
		);
		expect(events).toEqual([
			{ event: 'token', data: '{"text":"Hi"}' },
			{ event: 'end', data: '{"crisis":false}' }
		]);
	});

	it('reassembles events split across chunks', async () => {
		const events = await collect(streamOf('event: tok', 'en\ndata: {"te', 'xt":"a"}\n', '\n'));
		expect(events).toEqual([{ event: 'token', data: '{"text":"a"}' }]);
	});

	it('handles CRLF, comments and a missing final blank line', async () => {
		const events = await collect(streamOf(': ping\r\n\r\nevent: end\r\ndata: {}'));
		expect(events).toEqual([{ event: 'end', data: '{}' }]);
	});
});
