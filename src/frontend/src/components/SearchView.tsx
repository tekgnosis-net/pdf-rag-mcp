import {
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useDisclosure
} from "@chakra-ui/react";
import axios from "axios";
import { ChangeEvent, useMemo, useState } from "react";

interface SearchResult {
  document_id: number;
  title: string;
  similarity: number;
  chunk_index: number;
  text: string;
}

export const SearchView = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedMarkdown, setSelectedMarkdown] = useState<string | null>(null);
  const [selectedTitle, setSelectedTitle] = useState<string>("");
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleQueryChange = (event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      return;
    }
    setIsSearching(true);
    try {
      const { data } = await axios.get("/api/search", { params: { query } });
      setResults(data.matches ?? []);
    } finally {
      setIsSearching(false);
    }
  };

  const handleViewMarkdown = async (documentId: number, title: string) => {
    const { data } = await axios.get("/api/markdown", { params: { document_id: documentId } });
    setSelectedMarkdown(data.markdown ?? "Markdown not found.");
    setSelectedTitle(title);
    onOpen();
  };

  const bestMatches = useMemo(() => results.slice(0, 10), [results]);

  return (
    <Stack spacing={6}>
      <Heading size="lg">Search Processed PDFs</Heading>
      <Flex gap={4} align="flex-end">
        <FormControl>
          <FormLabel>Query</FormLabel>
          <Input placeholder="Ask a question" value={query} onChange={handleQueryChange} />
        </FormControl>
        <Button colorScheme="teal" onClick={handleSearch} isLoading={isSearching}>
          Search
        </Button>
      </Flex>

      <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
        <Table variant="simple">
          <Thead bg="gray.50">
            <Tr>
              <Th>Title</Th>
              <Th>Similarity</Th>
              <Th>Snippet</Th>
              <Th>Action</Th>
            </Tr>
          </Thead>
          <Tbody>
            {bestMatches.length === 0 && (
              <Tr>
                <Td colSpan={4}>
                  <Text color="gray.500">No matches yet. Submit a query to begin.</Text>
                </Td>
              </Tr>
            )}
            {bestMatches.map((match: SearchResult) => (
              <Tr key={`${match.document_id}-${match.chunk_index}`}>
                <Td>{match.title}</Td>
                <Td>{match.similarity.toFixed(3)}</Td>
                <Td>
                  <Text noOfLines={3}>{match.text}</Text>
                </Td>
                <Td>
                  <Button variant="outline" size="sm" onClick={() => void handleViewMarkdown(match.document_id, match.title)}>
                    View markdown
                  </Button>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      <Modal isOpen={isOpen} onClose={onClose} size="4xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>{selectedTitle}</ModalHeader>
          <ModalBody>
            <Box as="pre" whiteSpace="pre-wrap" fontSize="sm" p={4} bg="gray.900" color="green.200" borderRadius="md" overflowX="auto">
              {selectedMarkdown}
            </Box>
          </ModalBody>
        </ModalContent>
      </Modal>
    </Stack>
  );
};
