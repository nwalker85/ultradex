<script lang="ts">
  import type { Snippet } from "svelte";
  import TopBar from "./TopBar.svelte";
  import LeftNav from "./LeftNav.svelte";

  let { children }: { children: Snippet } = $props();
</script>

<div class="ccc-app-shell">
  <LeftNav />
  <div class="ccc-app-shell__column">
    <TopBar />
    <main class="ccc-app-shell__main">
      {@render children()}
    </main>
  </div>
</div>

<style>
  .ccc-app-shell {
    display: flex;
    height: 100dvh;
    overflow: hidden;
  }

  .ccc-app-shell__column {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
  }

  .ccc-app-shell__main {
    flex: 1;
    overflow: auto;
  }
</style>
