import {
  useLayoutEffect2
} from "./chunk-HNIB4NJS.js";
import {
  require_react
} from "./chunk-PSS62N5V.js";
import {
  __toESM
} from "./chunk-DC5AMYBS.js";

// ../node_modules/@radix-ui/react-id/dist/index.mjs
var React = __toESM(require_react(), 1);
var useReactId = React[" useId ".trim().toString()] || (() => void 0);
var count = 0;
function useId(deterministicId) {
  const [id, setId] = React.useState(useReactId());
  useLayoutEffect2(() => {
    if (!deterministicId) setId((reactId) => reactId ?? String(count++));
  }, [deterministicId]);
  return deterministicId || (id ? `radix-${id}` : "");
}

export {
  useId
};
//# sourceMappingURL=chunk-G5MWTKXP.js.map
