import { useEffect, useState } from "react";
import axios from "axios";
import {
  Container,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Flex,
  Heading,
  Spacer,
  Button,
  Link,
  Badge,
  Text,
  Box,
} from "@chakra-ui/react";
import { ExternalLinkIcon } from "@chakra-ui/icons";
import { ProcessingDashboard } from "@/components/ProcessingDashboard";
import { SearchView } from "@/components/SearchView";

const App = () => {
  const buildVersion = (import.meta.env.VITE_APP_VERSION as string | undefined) ?? __APP_VERSION__ ?? "dev";
  const [runtimeVersion, setRuntimeVersion] = useState<string | null>(null);
  const currentYear = new Date().getFullYear();

  useEffect(() => {
    let isMounted = true;
    axios
      .get<{ version?: string }>("/api/meta")
      .then(({ data }) => {
        const next = data.version?.trim();
        if (isMounted && next) {
          setRuntimeVersion(next);
        }
      })
      .catch(() => {
        /* ignore meta failures; fallback covers badge */
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const appVersion = runtimeVersion ?? buildVersion;

  return (
    <Container maxW="6xl" py={6}>
      <Flex align="center" mb={6} gap={3}>
        <Heading as="h1" size="lg">
          PDF-RAG MCP Server
        </Heading>
        <Badge colorScheme="teal" variant="subtle">
          v{appVersion}
        </Badge>
        <Spacer />
        <Link href="https://github.com/tekgnosis-net/pdf-rag-mcp" isExternal>
          <Button colorScheme="teal" rightIcon={<ExternalLinkIcon />}>GitHub</Button>
        </Link>
      </Flex>

      <Tabs variant="enclosed" colorScheme="teal" isFitted>
        <TabList>
          <Tab>Process PDFs</Tab>
          <Tab>Search Knowledge Base</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <ProcessingDashboard />
          </TabPanel>
          <TabPanel>
            <SearchView />
          </TabPanel>
        </TabPanels>
      </Tabs>

      <Box as="footer" mt={12} textAlign="center">
        <Text color="gray.500">© {currentYear} Tekgnosis Pty Ltd</Text>
      </Box>
    </Container>
  );
};

export default App;
