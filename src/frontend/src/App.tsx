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
} from "@chakra-ui/react";
import { ExternalLinkIcon } from "@chakra-ui/icons";
import { ProcessingDashboard } from "@/components/ProcessingDashboard";
import { SearchView } from "@/components/SearchView";

const App = () => {
  return (
    <Container maxW="6xl" py={6}>
      <Flex align="center" mb={6}>
        <Heading as="h1" size="lg">
          PDF-RAG MCP Server
        </Heading>
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
    </Container>
  );
};

export default App;
