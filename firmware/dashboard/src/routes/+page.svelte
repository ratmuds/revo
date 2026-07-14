<script lang="ts">
  import * as Resizable from "$lib/components/ui/resizable/index.js";
  import ThreeViewer from "$lib/components/ThreeViewer.svelte";
</script>

<Resizable.PaneGroup
  direction="horizontal"
  class="w-max h-vh rounded-lg border"
>
  <Resizable.Pane defaultSize={50}>
    <ThreeViewer />
  </Resizable.Pane>
  <Resizable.Handle />
  <Resizable.Pane defaultSize={50}>
    <div class="flex h-max items-center justify-center p-6">
      <span class="font-semibold">One</span>
    </div>
  </Resizable.Pane>
</Resizable.PaneGroup>
