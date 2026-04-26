module.exports = {
  comment: async (github, context, jsonPath) => {
    const { execSync } = require('child_process');
    const md = execSync(`python -m src.eval_harness.reporter --in=${jsonPath} --baseline=main`).toString();
    await github.rest.issues.createComment({
      owner: context.repo.owner, repo: context.repo.repo,
      issue_number: context.issue.number, body: md,
    });
  },
};
