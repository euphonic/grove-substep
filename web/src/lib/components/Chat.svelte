<script lang="ts">
	import { tick } from 'svelte';
	import type { ChatMessage } from '#lib/api.js';
	import { parseSSE } from '#lib/sse.js';

	let { threadId, initial }: { threadId: string; initial: ChatMessage[] } = $props();

	type Shown = ChatMessage & { crisis?: boolean };
	// Seeded once per thread; the page keys this component by thread id.
	// svelte-ignore state_referenced_locally
	let messages: Shown[] = $state([...initial]);
	let draft = $state('');
	let streaming = $state(false);
	let failure = $state<string | null>(null);
	let list: HTMLElement | undefined = $state();

	async function scrollDown() {
		await tick();
		list?.lastElementChild?.scrollIntoView({ block: 'end' });
	}

	async function send(event: SubmitEvent) {
		event.preventDefault();
		const text = draft.trim();
		if (!text || streaming) return;
		draft = '';
		failure = null;
		streaming = true;
		messages.push({ role: 'user', content: text });
		messages.push({ role: 'assistant', content: '' });
		const reply = messages[messages.length - 1];
		await scrollDown();
		try {
			const res = await fetch('/session/stream', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ threadId, text })
			});
			if (!res.ok || !res.body) throw new Error(`status ${res.status}`);
			for await (const { event: name, data } of parseSSE(res.body)) {
				const payload = JSON.parse(data) as { text?: string; crisis?: boolean; message?: string };
				if (name === 'token' && payload.text) {
					reply.content += payload.text;
					await scrollDown();
				} else if (name === 'end') {
					reply.crisis = payload.crisis === true;
				} else if (name === 'error') {
					throw new Error(payload.message ?? 'error');
				}
			}
		} catch {
			if (!reply.content) messages.pop();
			failure = 'That message did not go through. Please try again.';
		} finally {
			streaming = false;
		}
	}
</script>

<div class="flex min-h-[60dvh] flex-col gap-4">
	<ol bind:this={list} class="flex flex-1 flex-col gap-3" aria-live="polite">
		{#if messages.length === 0}
			<li class="text-grove-700">How are you arriving today?</li>
		{/if}
		{#each messages as m, i (i)}
			<li
				class={m.role === 'user'
					? 'max-w-[85%] self-end rounded-2xl bg-grove-700 px-4 py-2 text-white'
					: 'max-w-[85%] self-start rounded-2xl bg-white px-4 py-2 whitespace-pre-line shadow-sm' +
						(m.crisis ? ' border-l-4 border-amber-500' : '')}
			>
				{#if m.content}{m.content}{:else}<span class="text-grove-700">…</span>{/if}
			</li>
		{/each}
	</ol>

	{#if failure}<p class="text-sm text-red-700" role="alert">{failure}</p>{/if}

	<form onsubmit={send} class="sticky bottom-0 flex gap-2 bg-grove-50 py-2">
		<label class="sr-only" for="chat-input">Message</label>
		<textarea
			id="chat-input"
			bind:value={draft}
			rows="2"
			maxlength="8000"
			placeholder="Write whatever is on your mind"
			class="flex-1 resize-none rounded-lg border border-grove-100 bg-white px-3 py-2"
			onkeydown={(e) => {
				if (e.key === 'Enter' && !e.shiftKey) {
					e.preventDefault();
					(e.currentTarget.form as HTMLFormElement).requestSubmit();
				}
			}}></textarea>
		<button
			class="rounded-lg bg-grove-700 px-4 py-2 text-white disabled:opacity-50"
			disabled={streaming || !draft.trim()}
		>
			Send
		</button>
	</form>
</div>
