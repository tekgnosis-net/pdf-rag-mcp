import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  Button,
  Flex,
  Heading,
  HStack,
  IconButton,
  Input,
  Progress,
  Stack,
  Text,
  Tooltip,
  useColorMode
} from "@chakra-ui/react";
import { ArrowUpIcon, MoonIcon, RepeatIcon, SunIcon } from "@chakra-ui/icons";
import { ChangeEvent, useRef } from "react";
import { ProcessingJob, useProcessingQueue } from "@/hooks/useProcessingQueue";

const JobList = ({ title, jobs }: { title: string; jobs: ProcessingJob[] }) => (
  <Box>
    <Heading size="md" mb={3}>
      {title}
    </Heading>
    <Stack spacing={3}>
      {jobs.length === 0 && <Text color="gray.500">No entries</Text>}
      {jobs.map((job) => (
        <Box key={job.id} borderWidth="1px" borderRadius="md" p={4} shadow="sm">
          <Flex justify="space-between" align="center" mb={2}>
            <Text fontWeight="semibold">{job.filename}</Text>
            <Text fontSize="sm" color="gray.500">
              {job.status.toUpperCase()}
            </Text>
          </Flex>
          {job.status === "processing" && (
            <Progress value={job.progress} size="sm" colorScheme="teal" />
          )}
          {job.status === "queued" && (
            <Text fontSize="sm" color="gray.500">
              Waiting for processing
            </Text>
          )}
          {job.status === "completed" && (
            <Text fontSize="sm" color="green.500">
              Document processed
            </Text>
          )}
          {job.status === "failed" && (
            <Text fontSize="sm" color="red.500">
              {job.error ?? "Processing failed"}
            </Text>
          )}
        </Box>
      ))}
    </Stack>
  </Box>
);

export const ProcessingDashboard = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { queue, inProgress, completed, failed, enqueueFiles, refresh, isUploading, error } = useProcessingQueue();
  const { colorMode, toggleColorMode } = useColorMode();

  const handleFileSelection = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files) {
      return;
    }
    await enqueueFiles(event.target.files);
    event.target.value = "";
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <Stack spacing={6}>
      <Flex justify="space-between" align="center">
        <Heading size="lg">PDF Processing Queue</Heading>
        <HStack spacing={2}>
          <Tooltip label="Refresh status">
            <IconButton aria-label="Refresh" icon={<RepeatIcon />} onClick={() => void refresh()} isDisabled={isUploading} />
          </Tooltip>
          <Tooltip label={colorMode === "light" ? "Switch to dark" : "Switch to light"}>
            <IconButton aria-label="Toggle color mode" icon={colorMode === "light" ? <MoonIcon /> : <SunIcon />} onClick={toggleColorMode} />
          </Tooltip>
          <Button colorScheme="teal" leftIcon={<ArrowUpIcon />} onClick={handleUploadClick} isLoading={isUploading} loadingText="Uploading">
            Upload PDFs
          </Button>
          <Input ref={fileInputRef} type="file" multiple accept="application/pdf" display="none" onChange={handleFileSelection} />
        </HStack>
      </Flex>

      {error && (
        <Alert status="warning" variant="subtle">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Stack spacing={10}>
        <JobList title="In Progress" jobs={inProgress} />
        <JobList title="Queued" jobs={queue} />
        <JobList title="Completed" jobs={completed} />
        <JobList title="Failed" jobs={failed} />
      </Stack>
    </Stack>
  );
};
