export type SSEEvent = { event: string; data: string };

/** Parse a text/event-stream body into events. Handles events split across chunks. */
export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
	const reader = stream.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (value) buffer += decoder.decode(value, { stream: true });
			if (done) buffer += decoder.decode();
			buffer = buffer.replace(/\r\n/g, '\n');
			let sep: number;
			while ((sep = buffer.indexOf('\n\n')) !== -1) {
				const block = buffer.slice(0, sep);
				buffer = buffer.slice(sep + 2);
				const parsed = parseBlock(block);
				if (parsed) yield parsed;
			}
			if (done) {
				const tail = parseBlock(buffer);
				if (tail) yield tail;
				return;
			}
		}
	} finally {
		reader.releaseLock();
	}
}

function parseBlock(block: string): SSEEvent | null {
	let event = 'message';
	const data: string[] = [];
	for (const line of block.split('\n')) {
		if (!line || line.startsWith(':')) continue;
		const idx = line.indexOf(':');
		const field = idx === -1 ? line : line.slice(0, idx);
		const value = idx === -1 ? '' : line.slice(idx + 1).replace(/^ /, '');
		if (field === 'event') event = value;
		else if (field === 'data') data.push(value);
	}
	return data.length ? { event, data: data.join('\n') } : null;
}
